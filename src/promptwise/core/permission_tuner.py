"""permission_tuner — learn allow/deny rules from denial telemetry.

Consumes the denials JSONL the Phase 1 PermissionDenied handler writes
(``.promptwise/denials.jsonl``) and proposes permission rules:

* a command that is repeatedly denied AND scans clean (read-only-ish) -> suggest
  *alwaysAllow* to cut friction;
* a command that is repeatedly denied AND trips the security scanner -> suggest
  *alwaysDeny* to codify the block.

Already-allowed tools (read from ``.mcp.json``) are skipped. Pure stdlib +
existing SecurityScanner. Offline; proposals only — it never edits config.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


def _load_denials(path: Path) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _command_signature(rec: dict) -> str:
    """A coarse signature: tool + first command token (e.g. 'Bash:git')."""
    tool = (rec.get("tool_name") or "").strip() or "?"
    cmd = (rec.get("command") or "").strip()
    if not cmd:
        return tool
    first = re.split(r"\s+", cmd)[0]
    first = first.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]  # basename
    return f"{tool}:{first}" if first else tool


def _current_allowlist(mcp_json: Path) -> set[str]:
    if not mcp_json.exists():
        return set()
    try:
        data = json.loads(mcp_json.read_text(encoding="utf-8"))
    except Exception:
        return set()
    allowed: set[str] = set()
    for srv in (data.get("mcpServers") or {}).values():
        for name in srv.get("alwaysAllow", []) or []:
            allowed.add(str(name))
    return allowed


def tune_permissions(state_dir: str | Path = ".", min_count: int = 2,
                     mcp_json: str | Path | None = None) -> dict:
    state = Path(state_dir)
    denials_path = state / ".promptwise" / "denials.jsonl" if (state / ".promptwise").exists() else state / "denials.jsonl"
    records = _load_denials(denials_path)

    mcp_path = Path(mcp_json) if mcp_json else (state / ".mcp.json")
    allowed = _current_allowlist(mcp_path)

    sig_counts: Counter = Counter()
    sig_samples: dict[str, str] = {}
    for r in records:
        sig = _command_signature(r)
        sig_counts[sig] += 1
        sig_samples.setdefault(sig, r.get("command") or r.get("reason") or "")

    # classify with the existing scanner
    try:
        from promptwise.security.scanner import SecurityScanner
        scanner = SecurityScanner()
    except Exception:
        scanner = None

    suggestions = []
    for sig, count in sig_counts.most_common():
        if count < min_count:
            continue
        sample = sig_samples.get(sig, "")
        tool = sig.split(":", 1)[0]
        if tool in allowed:
            continue  # already always-allowed
        risky = False
        if scanner and sample:
            try:
                risky = scanner.check(sample).blocked
            except Exception:
                risky = False
        suggestions.append({
            "signature": sig,
            "denied_count": count,
            "sample": sample[:200],
            "proposed_rule": "alwaysDeny" if risky else "alwaysAllow",
            "rationale": ("repeatedly denied and trips the security scanner — codify the block"
                          if risky else
                          "repeatedly denied but scans clean — allow to reduce friction"),
        })

    return {
        "denials_path": str(denials_path),
        "total_denials": len(records),
        "distinct_signatures": len(sig_counts),
        "already_allowed": sorted(allowed),
        "suggestions": suggestions,
    }
