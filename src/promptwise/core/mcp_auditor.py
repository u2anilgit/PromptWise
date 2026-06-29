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
