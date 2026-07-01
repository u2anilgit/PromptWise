"""hook_bridge — runtime enforcement glue for Claude Code lifecycle hooks.

Turns PromptWise's *pull-based* governance (tools the agent may call) into
*push-based* enforcement (checks that fire automatically and can block). It does
this by importing the SAME core engines the MCP server uses — SecurityScanner,
AuditLog, Policy, QualityGate — so there are **zero edits to server.py** and no
second MCP process is spawned.

Design contract
---------------
* **Fail-open, always.** Any internal error returns an allow/no-op decision. A
  hook must never wedge the user's session.
* **No external infra.** Stdlib + existing core modules only. State persists to a
  project-local ``.promptwise/`` directory (audit JSONL, a session tool-call
  counter, a denials log). No database server, no network.
* **Additive.** Nothing here is imported by server.py; the MCP surface is
  unchanged. The Claude Code plugin invokes the thin scripts in ``hooks/``.

Hook → engine map (mirrors the existing MCP tools):
    UserPromptSubmit         -> Policy + SecurityScanner   (check_policy / security_check)
    PreToolUse(Write|Edit)   -> SecurityScanner            (security_check + prompt_injection)
    PreToolUse(any)          -> tool-call budget counter   (runaway-loop guard)
    PostToolUse(Write|Edit)  -> AuditLog.append            (record_audit, hash-chained)
    Stop                     -> QualityGate                (run_quality_gate, advisory)
    PermissionDenied         -> denials telemetry          (feeds Phase 4 permission_tuner)
    SessionEnd               -> AuditLog.export            (export_audit)
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── repo root (src/promptwise/core/hook_bridge.py -> parents[3]) ──────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Per-session tool-call ceiling (runaway-loop guard). Override via env.
_DEFAULT_TOOL_CALL_CEILING = 250


@dataclass
class HookDecision:
    """Normalised result returned by every hook handler.

    action: "allow" (proceed), "warn" (proceed, surface a note), "block" (stop).
    """
    action: str = "allow"
    reason: str = ""
    event: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"action": self.action, "reason": self.reason, "event": self.event, "extra": dict(self.extra)}


# ── helpers ──────────────────────────────────────────────────────────────────
def _state_dir(payload: dict) -> Path:
    """Project-local state dir; falls back to the repo root, then cwd."""
    cwd = payload.get("cwd") or "."
    try:
        d = Path(cwd) / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        d = _REPO_ROOT / ".promptwise"
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return d


def _tool_input(payload: dict) -> dict:
    ti = payload.get("tool_input")
    return ti if isinstance(ti, dict) else {}


def _edited_text(tool_input: dict) -> str:
    """Pull the content a Write/Edit would put on disk."""
    parts = []
    for key in ("content", "new_string", "new_str", "file_text"):
        v = tool_input.get(key)
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(parts)


def _policy_path() -> Path:
    return _REPO_ROOT / "config" / "policy.yaml"


# ── handlers (each fail-open) ────────────────────────────────────────────────
def pretooluse_scan(payload: dict) -> HookDecision:
    """Block a Write/Edit whose content trips the security scanner (secrets,
    destructive commands, supply-chain, injection)."""
    try:
        from promptwise.security.scanner import SecurityScanner
        text = _edited_text(_tool_input(payload))
        if not text.strip():
            return HookDecision(action="allow", event="PreToolUse")
        res = SecurityScanner().check(text)
        if getattr(res, "blocked", False):
            details = "; ".join(v.get("check", "?") for v in (res.violations or [])) or res.details
            return HookDecision(
                action="block", event="PreToolUse",
                reason=f"PromptWise blocked write: {details} (risk {res.risk_score}).",
                extra={"risk_score": res.risk_score, "violations": res.violations},
            )
        if res.violations:
            return HookDecision(
                action="warn", event="PreToolUse",
                reason=f"PromptWise security concerns: {res.details} (risk {res.risk_score}).",
                extra={"risk_score": res.risk_score},
            )
        return HookDecision(action="allow", event="PreToolUse")
    except Exception as e:  # fail-open
        return HookDecision(action="allow", event="PreToolUse", extra={"hook_error": f"{type(e).__name__}: {e}"})


def userpromptsubmit_policy(payload: dict) -> HookDecision:
    """Evaluate the submitted prompt against policy + injection scan before work
    begins. Warns by default; blocks only on a banned operation or hard injection."""
    try:
        prompt = payload.get("prompt") or payload.get("user_prompt") or ""
        if not isinstance(prompt, str) or not prompt.strip():
            return HookDecision(action="allow", event="UserPromptSubmit")

        notes: list[str] = []
        blocked = False

        # 1) banned-operation check via the same Policy engine the server uses.
        try:
            from promptwise.core.policy import Policy
            pp = _policy_path()
            if pp.exists():
                pol = Policy.from_yaml(pp)
                low = prompt.lower()
                for op in pol.banned_operations:
                    token = op.replace("_", " ")
                    if op in low or token in low:
                        dec = pol.evaluate_action(operation=op)
                        if not dec.allowed:
                            blocked = True
                            notes.append(f"banned operation referenced: '{op}'")
        except Exception:
            pass  # policy optional / fail-open

        # 2) injection / secret scan of the prompt itself (advisory).
        try:
            from promptwise.security.scanner import SecurityScanner
            res = SecurityScanner().check(prompt)
            inj = [v for v in (res.violations or []) if v.get("check") in ("injection", "syntax")]
            if inj:
                notes.append(f"possible prompt-injection ({len(inj)} pattern(s))")
        except Exception:
            pass

        if blocked:
            return HookDecision(action="block", event="UserPromptSubmit",
                                reason="PromptWise policy: " + "; ".join(notes), extra={"notes": notes})
        if notes:
            return HookDecision(action="warn", event="UserPromptSubmit",
                                reason="PromptWise advisory: " + "; ".join(notes), extra={"notes": notes})
        return HookDecision(action="allow", event="UserPromptSubmit")
    except Exception as e:
        return HookDecision(action="allow", event="UserPromptSubmit", extra={"hook_error": f"{type(e).__name__}: {e}"})


def tool_call_budget(payload: dict) -> HookDecision:
    """Per-session tool-call ceiling to curb runaway loops. Counter is a small
    JSON file keyed by session id under the project .promptwise/ dir."""
    try:
        import os
        ceiling = int(os.environ.get("PROMPTWISE_TOOL_CALL_CEILING", _DEFAULT_TOOL_CALL_CEILING))
        if ceiling <= 0:
            return HookDecision(action="allow", event="PreToolUse")
        session = str(payload.get("session_id") or "default")
        counter_file = _state_dir(payload) / "tool_call_counts.json"
        counts = {}
        if counter_file.exists():
            try:
                counts = json.loads(counter_file.read_text(encoding="utf-8")) or {}
            except Exception:
                counts = {}
        n = int(counts.get(session, 0)) + 1
        counts[session] = n
        try:
            counter_file.write_text(json.dumps(counts), encoding="utf-8")
        except Exception:
            pass
        if n > ceiling:
            return HookDecision(
                action="block", event="PreToolUse",
                reason=f"PromptWise tool-call budget exceeded: {n} > {ceiling} this session "
                       f"(raise PROMPTWISE_TOOL_CALL_CEILING or start a fresh session).",
                extra={"count": n, "ceiling": ceiling},
            )
        if n > 0.9 * ceiling:
            return HookDecision(action="warn", event="PreToolUse",
                                reason=f"PromptWise tool-call budget at {n}/{ceiling}.",
                                extra={"count": n, "ceiling": ceiling})
        return HookDecision(action="allow", event="PreToolUse", extra={"count": n, "ceiling": ceiling})
    except Exception as e:
        return HookDecision(action="allow", event="PreToolUse", extra={"hook_error": f"{type(e).__name__}: {e}"})


def posttooluse_audit(payload: dict) -> HookDecision:
    """Append a hash-chained audit record for every Write/Edit — the trace."""
    try:
        from promptwise.core.audit_log import AuditLog
        ti = _tool_input(payload)
        file_path = ti.get("file_path") or ti.get("path") or ""
        tool_name = payload.get("tool_name") or "edit"
        audit_file = _state_dir(payload) / "audit.jsonl"
        log = AuditLog(audit_file)
        rec = log.append(
            task=f"{tool_name} {file_path}".strip(),
            agent="claude-code",
            files_touched=[file_path] if file_path else [],
            rules_applied=["posttooluse_audit"],
        )
        ok, msg = log.verify()
        return HookDecision(action="allow", event="PostToolUse",
                            extra={"index": rec.index, "hash": rec.hash, "chain_ok": ok, "chain_msg": msg})
    except Exception as e:
        return HookDecision(action="allow", event="PostToolUse", extra={"hook_error": f"{type(e).__name__}: {e}"})


def stop_quality_gate(payload: dict) -> HookDecision:
    """Advisory quality-gate decision at the end of a turn. No findings are
    available from the Stop event, so this emits a recorded PASS/advisory and
    surfaces the audit chain status — never blocks."""
    try:
        from promptwise.core.quality_gate import QualityGate
        from promptwise.core.audit_log import AuditLog
        audit_file = _state_dir(payload) / "audit.jsonl"
        edits = 0
        chain_ok = True
        if audit_file.exists():
            log = AuditLog(audit_file)
            edits = len(log.records)
            chain_ok, _ = log.verify()
        findings = [] if chain_ok else [{"severity": "high", "detail": "audit chain broken"}]
        res = QualityGate().evaluate(story_id="session", findings=findings,
                                     risk_score=0 if chain_ok else 100)
        return HookDecision(action="warn" if res.decision != "PASS" else "allow", event="Stop",
                            reason=f"Quality gate: {res.decision} ({edits} change(s) recorded, chain_ok={chain_ok}).",
                            extra={"decision": res.decision, "edits": edits, "chain_ok": chain_ok})
    except Exception as e:
        return HookDecision(action="allow", event="Stop", extra={"hook_error": f"{type(e).__name__}: {e}"})


def permissiondenied_log(payload: dict) -> HookDecision:
    """Record a permission denial so Phase 4's permission_tuner can learn rules.
    Append-only JSONL telemetry; never blocks."""
    try:
        import time
        ti = _tool_input(payload)
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool_name": payload.get("tool_name", ""),
            "reason": payload.get("reason") or payload.get("permission_reason", ""),
            "command": ti.get("command") or ti.get("file_path") or "",
        }
        f = _state_dir(payload) / "denials.jsonl"
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        return HookDecision(action="allow", event="PermissionDenied", extra=rec)
    except Exception as e:
        return HookDecision(action="allow", event="PermissionDenied", extra={"hook_error": f"{type(e).__name__}: {e}"})


def _project_name(payload: dict) -> str:
    """Best-effort project label from the session cwd (basename)."""
    try:
        cwd = payload.get("cwd") or "."
        name = Path(cwd).name
        return name or ""
    except Exception:
        return ""


def sessionstart_replay(payload: dict) -> HookDecision:
    """On session start / resume, surface the most relevant recent corrections as
    context the model sees before any work begins. Turns the pull-based learning
    store into a push. Local SQLite only; never blocks."""
    try:
        import os
        k = int(os.environ.get("PROMPTWISE_REPLAY_K", "5"))
        if k <= 0:
            return HookDecision(action="allow", event="SessionStart")
        from promptwise.core.learning_store import LearningStore
        from promptwise.core.learning_replay import _format_reminder
        store = LearningStore()
        project = _project_name(payload)
        hits = store.recent(k=k, project=project) if project else store.recent(k=k)
        if not hits and project:
            hits = store.recent(k=k)  # fall back to global if none for this project
        reminder = _format_reminder(hits)
        if not reminder:
            return HookDecision(action="allow", event="SessionStart")
        return HookDecision(action="inject", event="SessionStart", reason=reminder,
                            extra={"matched": len(hits), "project": project})
    except Exception as e:  # fail-open
        return HookDecision(action="allow", event="SessionStart", extra={"hook_error": f"{type(e).__name__}: {e}"})


def precompact_guard(payload: dict) -> HookDecision:
    """Before the context is compacted, inject a note that preserves the governance
    state — audit-chain status and the files under audit — so it survives the
    summary. Advisory context only; never blocks."""
    try:
        from promptwise.core.audit_log import AuditLog
        audit_file = _state_dir(payload) / "audit.jsonl"
        if not audit_file.exists():
            return HookDecision(action="allow", event="PreCompact")
        log = AuditLog(audit_file)
        records = log.records
        if not records:
            return HookDecision(action="allow", event="PreCompact")
        ok, _ = log.verify()
        files: list[str] = []
        for rec in records[-8:]:
            for f in (getattr(rec, "files_touched", None) or []):
                if f and f not in files:
                    files.append(f)
        parts = [
            "Preserve across compaction — PromptWise governance state:",
            f"- Audit chain: {len(records)} recorded change(s), chain_ok={ok}.",
        ]
        if files:
            parts.append("- Files under audit: " + ", ".join(files[:12]) + ".")
        parts.append("- Keep the audit trail intact; do not discard governance context.")
        return HookDecision(action="inject", event="PreCompact", reason="\n".join(parts),
                            extra={"records": len(records), "chain_ok": ok, "files": files[:12]})
    except Exception as e:  # fail-open
        return HookDecision(action="allow", event="PreCompact", extra={"hook_error": f"{type(e).__name__}: {e}"})


def sessionend_export(payload: dict) -> HookDecision:
    """Emit the portable trace for the session on the way out."""
    try:
        from promptwise.core.audit_log import AuditLog
        audit_file = _state_dir(payload) / "audit.jsonl"
        if not audit_file.exists():
            return HookDecision(action="allow", event="SessionEnd")
        log = AuditLog(audit_file)
        ok, msg = log.verify()
        out = _state_dir(payload) / "audit_export.json"
        try:
            out.write_text(log.export_json(), encoding="utf-8")
        except Exception:
            pass
        return HookDecision(action="allow", event="SessionEnd",
                            extra={"records": len(log.records), "chain_ok": ok, "chain_msg": msg, "export": str(out)})
    except Exception as e:
        return HookDecision(action="allow", event="SessionEnd", extra={"hook_error": f"{type(e).__name__}: {e}"})


_HANDLERS = {
    "pretooluse_scan": pretooluse_scan,
    "userpromptsubmit_policy": userpromptsubmit_policy,
    "tool_call_budget": tool_call_budget,
    "posttooluse_audit": posttooluse_audit,
    "stop_quality_gate": stop_quality_gate,
    "permissiondenied_log": permissiondenied_log,
    "sessionstart_replay": sessionstart_replay,
    "precompact_guard": precompact_guard,
    "sessionend_export": sessionend_export,
}


def dispatch(handler_key: str, payload: dict) -> HookDecision:
    fn = _HANDLERS.get(handler_key)
    if fn is None:
        return HookDecision(action="allow", reason=f"unknown handler {handler_key}")
    return fn(payload or {})


def run(handler_key: str, *, stdin=None, stdout=None, stderr=None) -> int:
    """CLI entry used by the thin hooks/ scripts.

    Reads the Claude Code hook JSON on stdin, runs the handler, and emits a
    Claude-Code-compatible result:
      * block  -> reason on stderr, exit code 2 (Claude Code blocks the action)
      * warn   -> advisory JSON on stdout, exit 0
      * inject -> context JSON on stdout, exit 0 (feed text into the session)
      * allow  -> exit 0 (silent)
    ANY failure path returns exit 0 (fail-open).
    """
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        raw = stdin.read()
        payload = json.loads(raw) if raw and raw.strip() else {}
    except Exception:
        return 0  # unreadable input -> never wedge
    try:
        decision = dispatch(handler_key, payload)
    except Exception:
        return 0
    try:
        if decision.action == "block":
            stderr.write((decision.reason or "PromptWise hook blocked the action.") + "\n")
            return 2
        if decision.action in ("warn", "inject"):
            if not (decision.reason or "").strip():
                return 0  # nothing to surface
            stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": decision.event,
                    "additionalContext": decision.reason,
                }
            }) + "\n")
            return 0
    except Exception:
        return 0
    return 0
