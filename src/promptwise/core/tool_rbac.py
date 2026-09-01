"""core.tool_rbac -- per-call RBAC for remote MCP tool calls.

Applies ONLY to remote (HTTP-transport) connections -- see server.py's
call_tool(), which checks core.session_context.get_current_remote_identity()
before ever consulting this module. Stdio/local calls never reach this
code path at all.

Fail-closed: config/mcp_tool_roles.yaml's tool_roles mapping is the only
source of viewer-eligible tools; anything absent from it (missing file,
parse error, or simply a tool nobody classified yet, including any
future tool added after this shipped) requires "admin" by default. This
mirrors dashboard/auth.py's load_ad_group_map/load_group_role_map
fail-closed pattern exactly.

See docs/superpowers/specs/2026-09-01-mcp-per-call-rbac-design.md for
how the initial config/mcp_tool_roles.yaml classification was generated
(a one-time naming-heuristic pass over all 140 tool names, with one
manual override -- get_admin_settings, which exposes org-sensitive
config despite matching the get_ viewer-prefix heuristic).
"""
from __future__ import annotations

from pathlib import Path

from promptwise.dashboard.auth import _ROLE_RANK


def load_tool_roles(path: str = "config/mcp_tool_roles.yaml") -> dict[str, str]:
    """Parse config/mcp_tool_roles.yaml's `tool_roles` mapping. Missing
    file, parse error, or an unrecognized role value yields {} / drops
    that entry -- fail-closed, since minimum_role_for's default for an
    absent tool is "admin"."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        raw = data.get("tool_roles", {}) or {}
        return {str(k): str(v) for k, v in raw.items() if str(v) in _ROLE_RANK}
    except Exception:
        return {}


def minimum_role_for(tool_name: str, tool_roles: dict[str, str]) -> str:
    """The minimum role required to call `tool_name`. Any tool not
    present in `tool_roles` (including every tool if the file failed to
    load) defaults to "admin" -- the fail-closed direction."""
    return tool_roles.get(tool_name, "admin")
