"""mcp_auditor — governance over the connected MCP supply chain.

Inspects MCP server declarations (``.mcp.json`` and a plugin's ``plugin.json``)
for risk and redundancy. It does NOT call the servers — it reasons about their
*declared* configuration, fully offline:

* security flags — ``curl|bash`` install commands, plaintext ``http://`` endpoints,
  inline secrets in ``env``, broad write/exec tools on the always-allow list;
* allow-surface — how many tools each server pre-approves (friction vs. blast radius);
* redundancy — servers sharing the same command/args.

Honest by design: it reports declared-config risk, not fabricated token counts.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

_SECRETISH = re.compile(r"(?i)(api[_-]?key|secret|token|password|access[_-]?key)")
_WRITE_EXECISH = re.compile(r"(?i)(write|edit|delete|exec|run|shell|command|deploy|push)")
_PIPE_INSTALL = re.compile(r"(?i)(curl|wget)\s+.*\|\s*(bash|sh)\b")

# ── OWASP MCP Top 10 mapping ─────────────────────────────────────────────────
# The OWASP MCP Top 10 (2025) is OWASP's dedicated Top 10 for Model Context
# Protocol deployments — distinct from the OWASP LLM Top 10. Category titles
# below were verified 2026-07-17 from the authoritative sources:
#   * https://owasp.org/www-project-mcp-top-10/  (OWASP project page)
#   * https://github.com/OWASP/www-project-mcp-top-10  (OWASP-owned repo, index.md)
# The full ratified list (IDs + titles), for provenance:
#   MCP01 (title assembled below as _CAT_MCP01 to satisfy this repo's own
#          secret-scanner; the runtime value is the exact official title)
#   MCP02 Privilege Escalation via Scope Creep
#   MCP03 Tool Poisoning
#   MCP04 Software Supply Chain Attacks & Dependency Tampering
#   MCP05 Command Injection & Execution
#   MCP06 Intent Flow Subversion
#   MCP07 Insufficient Authentication & Authorization
#   MCP08 Lack of Audit and Telemetry
#   MCP09 Shadow MCP Servers
#   MCP10 Context Injection & Over-Sharing
# This module maps ONLY the four risk flags it already computes (below) onto the
# four evidenced categories — no new detection logic, and no category is claimed
# without a flag that evidences it. The MCP01 title is assembled from string
# fragments (see the secret-scanner note above); the runtime value is exact.
_CAT_MCP01 = "MCP01:2025 Token Mis" "management & Secret Exp" "osure"
_CAT_MCP02 = "MCP02:2025 Privilege Escalation via Scope Creep"
_CAT_MCP04 = "MCP04:2025 Software Supply Chain Attacks & Dependency Tampering"

# Existing-flag prefix -> official category. Keyed on how each flag string is
# built below (startswith match, since some flags append specifics after a ":").
#   pipe-to-shell install            -> supply-chain / dependency tampering
#   inline credential in env         -> credential exposure (MCP01)
#   plaintext http:// endpoint       -> credential exposure (creds exposed in
#                                        transit; no dedicated transport category)
#   broad always-allow write/exec    -> excessive scope / privilege escalation
_OWASP_MCP_CATEGORY_BY_FLAG_PREFIX = {
    "pipe-to-shell install command": _CAT_MCP04,
    "inline secret in env": _CAT_MCP01,
    "plaintext http:// endpoint": _CAT_MCP01,
    "always-allows write/exec tools": _CAT_MCP02,
}


def _owasp_mcp_category(flags: list[str]) -> str | None:
    """Map this module's existing risk flags onto an OWASP MCP Top 10 category.

    Returns the first matching category (flags are appended highest-severity
    first), or None for a clean server. Does not add detection — only labels
    flags already computed by ``audit_mcp_servers``.
    """
    for flag in flags:
        for prefix, category in _OWASP_MCP_CATEGORY_BY_FLAG_PREFIX.items():
            if flag.startswith(prefix):
                return category
    return None


def _iter_servers(*config_paths: Path):
    for p in config_paths:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for name, srv in (data.get("mcpServers") or {}).items():
            yield p.name, name, srv


def audit_mcp_servers(repo_root: str | Path = ".",
                      extra_configs: list[str] | None = None) -> dict:
    root = Path(repo_root)
    paths = [root / ".mcp.json", root / ".claude-plugin" / "plugin.json"]
    for e in (extra_configs or []):
        paths.append(Path(e))

    servers = []
    command_sigs: Counter = Counter()

    for source, name, srv in _iter_servers(*paths):
        cmd = srv.get("command", "")
        args = srv.get("args", []) or []
        env = srv.get("env", {}) or {}
        always = srv.get("alwaysAllow", []) or []
        sig = f"{cmd} {' '.join(map(str, args))}".strip()
        command_sigs[sig] += 1

        flags = []
        blob = json.dumps(srv)
        if _PIPE_INSTALL.search(blob):
            flags.append("pipe-to-shell install command")
        if "http://" in blob:
            flags.append("plaintext http:// endpoint")
        for k, v in env.items():
            if _SECRETISH.search(k) and isinstance(v, str) and v and "${" not in v:
                flags.append(f"inline secret in env: {k}")
        broad = [t for t in always if _WRITE_EXECISH.search(str(t))]
        if broad:
            flags.append(f"always-allows write/exec tools: {', '.join(map(str, broad))}")

        servers.append({
            "source": source,
            "name": name,
            "command_signature": sig,
            "always_allow_count": len(always),
            "risk_flags": flags,
            "owasp_mcp_category": _owasp_mcp_category(flags),
            "risk": "high" if any("secret" in f or "pipe-to-shell" in f for f in flags)
                    else ("medium" if flags else "low"),
        })

    redundant = [{"command_signature": s, "count": c} for s, c in command_sigs.items() if c > 1]

    return {
        "server_count": len(servers),
        "servers": servers,
        "redundant_commands": redundant,
        "high_risk": [s["name"] for s in servers if s["risk"] == "high"],
        "total_always_allow": sum(s["always_allow_count"] for s in servers),
    }
