"""governor — policy-gated, reversible autonomous governance (Phase 9).

Turns insights recommendations (``core/insights.compute_recommendations``) into
typed, policy-gated, reversible **actions** that PromptWise can *propose* and — only
when explicitly opted in — *apply*, with a full hash-chained audit trail and a local
undo ledger.

Safety model (non-negotiable, this is the first component that can change user state):

* **Default advise-only.** ``PROMPTWISE_AUTONOMY`` in {``advise`` (default),
  ``dry_run``, ``apply``}. Nothing changes state unless ``apply`` is set explicitly.
* **Allowlist is the only path to state change.** Only ``AdjustBudgetGuard`` and
  ``WriteRoutingPreferenceNote`` (both ``safe``, both reversible, both writing local,
  *gitignored* overlays — never tracked config or live ``mcp.json``/permissions) can
  ever move state, and only in ``apply``. Everything else is ``advisory-only``:
  emitted as a proposal, never auto-applied in any mode.
* **Policy gate.** Every action is run through ``core/policy.Policy.evaluate_action``.
  A violation blocks the action (recorded, never applied). Warnings surface, not fatal.
* **Reversible + idempotent.** Every applied action writes an undo-ledger entry
  ``{action_id, type, prior_state, new_state, ts}``; ``undo(action_id)`` restores the
  exact prior state. Re-applying an already-applied action is a no-op.
* **Fail-safe.** Any error while applying an action rolls back its partial write and
  records NO ledger entry, leaving no partial state; sibling actions are unaffected.
* **Everything audited, everything offline.** Stdlib only, no network, no new deps.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # PyYAML is already a PromptWise dependency (policy/model registry use it)
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

from promptwise.core.audit_log import AuditLog
from promptwise.core.policy import Policy, PolicyDecision

# ── modes ─────────────────────────────────────────────────────────────────────
MODE_ADVISE = "advise"
MODE_DRY_RUN = "dry_run"
MODE_APPLY = "apply"
VALID_MODES = (MODE_ADVISE, MODE_DRY_RUN, MODE_APPLY)
ENV_MODE = "PROMPTWISE_AUTONOMY"

# ── action types ──────────────────────────────────────────────────────────────
TYPE_ADJUST_BUDGET = "AdjustBudgetGuard"
TYPE_ROUTING_NOTE = "WriteRoutingPreferenceNote"
TYPE_PERMISSION_RULE = "ProposePermissionRule"
TYPE_ADVISORY_NOTE = "AdvisoryNote"

# The ONLY action types that can ever move state (and only in apply mode). Both are
# reversible and write local, gitignored overlays — never tracked/live config.
ALLOWLISTED_TYPES: frozenset[str] = frozenset({TYPE_ADJUST_BUDGET, TYPE_ROUTING_NOTE})

# per-type policy operation label (so a policy can ban a specific autonomy action)
_OPERATION = {
    TYPE_ADJUST_BUDGET: "adjust_budget",
    TYPE_ROUTING_NOTE: "write_routing_preference",
    TYPE_PERMISSION_RULE: "propose_permission_rule",
    TYPE_ADVISORY_NOTE: "advisory_note",
}

# ── local, gitignored artifact locations (all under <root>/.promptwise) ───────
_STATE_DIR = ".promptwise"
_BUDGET_OVERLAY = "budget.local.yaml"          # mirrors models.local.yaml precedent
_ROUTING_NOTE = "routing_preferences.local.md"
_LEDGER = "governor_ledger.json"
_PROPOSALS = "governor_proposals.json"         # advisory artifact for humans/surfaces


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _default_root() -> Path:
    """Root whose ``.promptwise`` state dir matches the DB / BudgetGuardian location.

    ``get_db_path()`` is ``~/.promptwise/promptwise.db``; its grandparent is the home
    dir, so ``<home>/.promptwise`` == the ``~/.promptwise`` that ``BudgetGuardian`` reads
    for the budget overlay. Using this as the default keeps the governor's writes and the
    guardian's reads on the same file. Fail-soft to cwd if the DB path can't be resolved.
    """
    try:
        from promptwise.db.models import get_db_path
        return get_db_path().parent.parent
    except Exception:
        return Path(".")


# ── budget overlay helpers (module-level so BudgetGuardian / surfaces can reuse) ─
def _budget_overlay_path(root: str | Path) -> Path:
    return Path(root) / _STATE_DIR / _BUDGET_OVERLAY


def read_budget_overlay(root: str | Path | None = None) -> float | None:
    """Return the overlaid budget limit (USD) or ``None`` if no overlay exists.

    ``root=None`` resolves to the shared home state dir (see ``_default_root``) so this
    reads the same overlay ``BudgetGuardian`` does. Fail-open: a missing/unparseable
    overlay yields ``None`` (the caller falls back to its tracked default), never raises.
    """
    p = _budget_overlay_path(_default_root() if root is None else root)
    if not p.exists():
        return None
    try:
        if yaml is not None:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        else:  # pragma: no cover - yaml always present in practice
            data = json.loads(p.read_text(encoding="utf-8"))
        val = data.get("limit_usd")
        return float(val) if val is not None else None
    except Exception:
        return None


# ── action model ──────────────────────────────────────────────────────────────
@dataclass
class Action:
    """A typed, reversible governance action derived from one recommendation."""
    id: str
    type: str
    blast_radius: str          # "safe" | "advisory-only"
    category: str
    rec_id: str
    description: str
    params: dict = field(default_factory=dict)

    @property
    def operation(self) -> str:
        return _OPERATION.get(self.type, "governor_action")

    @property
    def allowlisted(self) -> bool:
        return self.type in ALLOWLISTED_TYPES and self.blast_radius == "safe"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "blast_radius": self.blast_radius,
            "category": self.category, "rec_id": self.rec_id,
            "description": self.description, "params": dict(self.params),
            "operation": self.operation, "allowlisted": self.allowlisted,
        }


def _classify(category: str) -> tuple[str, str]:
    """Map a recommendation category to (action_type, blast_radius)."""
    c = (category or "").lower()
    if c == "budget":
        return TYPE_ADJUST_BUDGET, "safe"
    if c in ("routing", "cost"):
        return TYPE_ROUTING_NOTE, "safe"
    if c in ("permission", "permissions"):
        return TYPE_PERMISSION_RULE, "advisory-only"
    # quality regressions + anything unknown: advisory-only (needs a human)
    return TYPE_ADVISORY_NOTE, "advisory-only"


def _budget_target(evidence: dict) -> float | None:
    """Derive the new budget limit from a budget recommendation's evidence."""
    kind = str(evidence.get("kind", ""))
    projected = evidence.get("projected_usd")
    limit = evidence.get("limit_usd")
    try:
        if projected is not None:
            projected = float(projected)
            if kind == "projected_overrun":
                # raise the cap to cover the projected spend
                return round(projected, 2)
            if kind == "projected_underrun":
                # lower the cap toward projected (with modest headroom)
                return round(max(projected * 1.2, 0.01), 2)
        if limit is not None:
            return round(float(limit), 2)
    except (TypeError, ValueError):
        return None
    return None


def propose(recommendations: list[dict]) -> list[Action]:
    """Map recommendations to typed, reversible actions (pure; no side effects)."""
    actions: list[Action] = []
    for rec in recommendations or []:
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        category = rec.get("category", "")
        rtype, radius = _classify(category)
        evidence = rec.get("evidence") or {}
        params: dict[str, Any] = {"evidence": evidence}

        if rtype == TYPE_ADJUST_BUDGET:
            target = _budget_target(evidence)
            if target is None or target <= 0:
                # cannot derive a concrete reversible effect -> demote to advisory
                rtype, radius = TYPE_ADVISORY_NOTE, "advisory-only"
            else:
                params["new_limit_usd"] = target
        if rtype == TYPE_ROUTING_NOTE:
            params["note"] = rec.get("message", "")

        actions.append(Action(
            id=str(rec["id"]), type=rtype, blast_radius=radius,
            category=str(category), rec_id=str(rec["id"]),
            description=str(rec.get("message", "")), params=params,
        ))
    return actions


# ── the governor ──────────────────────────────────────────────────────────────
class Governor:
    """Propose -> policy-gate -> (advise / dry_run / apply) with undo + audit."""

    def __init__(self, *, root: str | Path | None = None, mode: str | None = None,
                 policy: Policy | None = None, policy_path: str | Path | None = None,
                 audit_log: AuditLog | None = None,
                 audit_path: str | Path | None = None) -> None:
        # root=None -> shared home state dir, so applied budget overlays land where
        # BudgetGuardian reads them. Tests pass an explicit temp root for isolation.
        self.root = _default_root() if root is None else Path(root)
        self.mode = self._resolve_mode(mode)
        self.policy = self._resolve_policy(policy, policy_path)
        if audit_log is not None:
            self.audit = audit_log
        else:
            self.audit = AuditLog(audit_path) if audit_path is not None else AuditLog()

    # -- config resolution --
    @staticmethod
    def _resolve_mode(mode: str | None) -> str:
        m = (mode if mode is not None else os.environ.get(ENV_MODE, MODE_ADVISE))
        m = str(m).strip().lower()
        return m if m in VALID_MODES else MODE_ADVISE   # unknown -> conservative

    @staticmethod
    def _resolve_policy(policy: Policy | None, policy_path: str | Path | None) -> Policy:
        if policy is not None:
            return policy
        if policy_path is not None:
            p = Path(policy_path)
            if p.exists():
                try:
                    return Policy.from_yaml(p)
                except Exception:
                    pass
        return Policy.from_dict({})   # empty policy = allow all (permissive default)

    # -- paths --
    def _state_dir(self) -> Path:
        return self.root / _STATE_DIR

    def _ledger_path(self) -> Path:
        return self._state_dir() / _LEDGER

    def _routing_note_path(self) -> Path:
        return self._state_dir() / _ROUTING_NOTE

    def _proposals_path(self) -> Path:
        return self._state_dir() / _PROPOSALS

    def _ensure_state_dir(self) -> None:
        self._state_dir().mkdir(parents=True, exist_ok=True)

    # -- undo ledger (json store keyed by action id) --
    def ledger_entries(self) -> dict:
        p = self._ledger_path()
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def _write_ledger(self, entries: dict) -> None:
        self._ensure_state_dir()
        self._ledger_path().write_text(
            json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")

    def _ledger_record(self, action: Action, prior_state: dict, new_state: dict) -> None:
        entries = self.ledger_entries()
        entries[action.id] = {
            "action_id": action.id, "type": action.type,
            "prior_state": prior_state, "new_state": new_state, "ts": _now_iso(),
        }
        self._write_ledger(entries)

    def _ledger_remove(self, action_id: str) -> None:
        entries = self.ledger_entries()
        if action_id in entries:
            del entries[action_id]
            self._write_ledger(entries)

    # -- budget overlay --
    def write_budget_overlay(self, limit_usd: float) -> None:
        self._ensure_state_dir()
        p = _budget_overlay_path(self.root)
        payload = {"limit_usd": round(float(limit_usd), 4),
                   "_managed_by": "promptwise-governor", "_ts": _now_iso()}
        if yaml is not None:
            p.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
        else:  # pragma: no cover
            p.write_text(json.dumps(payload), encoding="utf-8")

    def _budget_prior(self) -> dict:
        p = _budget_overlay_path(self.root)
        raw = p.read_text(encoding="utf-8") if p.exists() else None
        return {"limit_usd": read_budget_overlay(self.root), "raw": raw}

    def _restore_raw(self, path: Path, prior: dict) -> None:
        """Restore a text-file overlay to its exact prior state (delete if absent)."""
        raw = prior.get("raw")
        if raw is None:
            if path.exists():
                path.unlink()
        else:
            self._ensure_state_dir()
            path.write_text(raw, encoding="utf-8")

    # -- routing note --
    def _routing_prior(self) -> dict:
        p = self._routing_note_path()
        raw = p.read_text(encoding="utf-8") if p.exists() else None
        return {"raw": raw}

    def _write_routing_note(self, action: Action, prior: dict) -> str:
        self._ensure_state_dir()
        p = self._routing_note_path()
        header = "# PromptWise routing-preference notes (advisory, machine-local)\n"
        body = prior.get("raw") or header
        line = f"- [{_now_iso()}] ({action.category}) {action.params.get('note', action.description)}\n"
        if line not in body:
            body = body + line
        p.write_text(body, encoding="utf-8")
        return body

    # -- fail-safe seam (overridable in tests): runs after the state write, before
    #    the ledger/audit commit, so a fault here triggers rollback.
    def _post_write_verify(self, action: Action) -> None:
        """Post-write verification hook. Default no-op. Exists as a seam so a fault
        injected here exercises the fail-safe rollback path in tests, and so future
        integrity checks can abort an apply before it is committed to the ledger."""
        return None

    # -- policy gate --
    def _gate(self, action: Action) -> PolicyDecision:
        return self.policy.evaluate_action(
            operation=action.operation,
            estimated_cost=0.0,          # governor actions do not themselves spend
            spent_so_far=0.0,
            model_tier=None,
            gates_passed=[],
        )

    # -- apply one allowlisted safe action (fail-safe) --
    def _apply_one(self, action: Action) -> dict:
        # idempotency: an already-applied action is a no-op
        if action.id in self.ledger_entries():
            return {"status": "noop"}

        if action.type == TYPE_ADJUST_BUDGET:
            overlay = _budget_overlay_path(self.root)
            prior = self._budget_prior()
            try:
                new_limit = float(action.params["new_limit_usd"])
                self.write_budget_overlay(new_limit)
                self._post_write_verify(action)          # seam (may raise)
            except Exception as exc:
                self._restore_raw(overlay, prior)         # roll back partial write
                return {"status": "failed", "error": str(exc)}
            new_state = {"limit_usd": round(new_limit, 4)}
            self._ledger_record(action, prior, new_state)
            return {"status": "applied", "new_state": new_state,
                    "files_touched": [str(overlay)]}

        if action.type == TYPE_ROUTING_NOTE:
            path = self._routing_note_path()
            prior = self._routing_prior()
            try:
                self._write_routing_note(action, prior)
                self._post_write_verify(action)           # seam (may raise)
            except Exception as exc:
                self._restore_raw(path, prior)            # roll back partial write
                return {"status": "failed", "error": str(exc)}
            new_state = {"note": action.params.get("note", action.description)}
            self._ledger_record(action, prior, new_state)
            return {"status": "applied", "new_state": new_state,
                    "files_touched": [str(path)]}

        # not an allowlisted, applyable type
        return {"status": "advisory"}

    # -- audit helper --
    def _audit(self, event: str, action: Action, *, verdict: PolicyDecision | None = None,
               files: list[str] | None = None) -> None:
        gate = "PASS"
        if verdict is not None and not verdict.allowed:
            gate = "FAIL"
        self.audit.append(
            f"governor:{event}:{action.id}",
            actor="promptwise",
            agent="promptwise-governor",
            rules_applied=[action.type, action.blast_radius, f"mode:{self.mode}"],
            gate_decision=gate,
            compliance_decision=f"governor:{event}",
            files_touched=files or [],
        )

    # -- public API --
    def run(self, recommendations: list[dict] | None = None) -> dict:
        """Propose, policy-gate, and (per mode) apply. Audits every event."""
        if recommendations is None:
            recommendations = self._compute_recommendations()
        actions = propose(recommendations)

        proposals: list[dict] = []
        applied: list[str] = []
        blocked: list[dict] = []
        advisory: list[str] = []
        would_apply: list[str] = []
        noop: list[str] = []
        failed: list[str] = []

        for action in actions:
            entry = action.to_dict()
            verdict = self._gate(action)
            entry["verdict"] = verdict.to_dict()

            # 1) policy gate — a violation blocks the action in every mode
            if not verdict.allowed:
                entry["status"] = "blocked"
                blocked.append({"action_id": action.id,
                                "violations": list(verdict.violations)})
                self._audit("blocked", action, verdict=verdict)
                proposals.append(entry)
                continue

            # 2) advisory-only actions are never auto-applied, in any mode
            if not action.allowlisted:
                entry["status"] = "advisory"
                advisory.append(action.id)
                self._audit("proposed", action, verdict=verdict)
                proposals.append(entry)
                continue

            # 3) allowlisted + safe + policy-ok
            if self.mode == MODE_APPLY:
                res = self._apply_one(action)
                status = res.get("status", "advisory")
                entry["status"] = status
                entry["result"] = res
                if status == "applied":
                    applied.append(action.id)
                    self._audit("applied", action, verdict=verdict,
                                files=res.get("files_touched"))
                elif status == "noop":
                    noop.append(action.id)
                    self._audit("noop", action, verdict=verdict)
                elif status == "failed":
                    failed.append(action.id)
                    self._audit("apply_failed", action, verdict=verdict)
                else:
                    advisory.append(action.id)
                    self._audit("proposed", action, verdict=verdict)
            else:
                # advise / dry_run: would apply, but change nothing
                entry["status"] = "would_apply"
                would_apply.append(action.id)
                self._audit("dry_run" if self.mode == MODE_DRY_RUN else "proposed",
                            action, verdict=verdict)
            proposals.append(entry)

        ok, msg = self.audit.verify()
        out = {
            "mode": self.mode,
            "proposals": proposals,
            "summary": {
                "proposed": len(proposals), "applied": applied, "blocked": blocked,
                "advisory": advisory, "would_apply": would_apply, "noop": noop,
                "failed": failed,
            },
            "audit_ok": ok, "audit_msg": msg,
        }
        self._emit_proposals_artifact(out)
        return out

    def undo(self, action_id: str) -> dict:
        """Restore the prior state recorded for ``action_id`` and audit it."""
        entries = self.ledger_entries()
        entry = entries.get(action_id)
        if not entry:
            return {"status": "noop", "reason": "no ledger entry"}

        atype = entry.get("type")
        prior = entry.get("prior_state") or {}
        files: list[str] = []
        if atype == TYPE_ADJUST_BUDGET:
            path = _budget_overlay_path(self.root)
            self._restore_raw(path, prior)
            files = [str(path)]
        elif atype == TYPE_ROUTING_NOTE:
            path = self._routing_note_path()
            self._restore_raw(path, prior)
            files = [str(path)]
        else:
            return {"status": "noop", "reason": f"non-reversible type {atype}"}

        self._ledger_remove(action_id)
        pseudo = Action(id=action_id, type=str(atype), blast_radius="safe",
                        category="", rec_id=action_id, description="undo")
        self._audit("undone", pseudo, files=files)
        return {"status": "undone", "action_id": action_id, "restored": prior}

    # -- optional: derive recommendations from local telemetry (offline) --
    def _compute_recommendations(self) -> list[dict]:
        try:
            from promptwise.core.insights import compute_recommendations
            return compute_recommendations()
        except Exception:
            return []

    def _emit_proposals_artifact(self, out: dict) -> None:
        """Write the proposals to a local advisory artifact (non-state-changing;
        for the dashboard/human). Fail-open — never blocks a run."""
        try:
            self._ensure_state_dir()
            self._proposals_path().write_text(
                json.dumps({"ts": _now_iso(), "mode": out["mode"],
                            "proposals": out["proposals"],
                            "summary": out["summary"]}, indent=2),
                encoding="utf-8")
        except Exception:
            pass
