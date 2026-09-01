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

# src/promptwise/core/tool_rbac.py -> parents[3] is the repo root, matching
# core/admin_config.py, core/doctor.py, core/hook_bridge.py, core/model_registry.py,
# core/effort_map.py's established idiom -- resolved from the package location,
# not the process cwd (a cwd-relative default silently loads {} -- and thus
# fail-closed admin-only for every tool -- for any deployment not launched
# from the repo root).
_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "mcp_tool_roles.yaml"


def load_tool_roles(path: str | None = None) -> dict[str, str]:
    """Parse config/mcp_tool_roles.yaml's `tool_roles` mapping. Missing
    file, parse error, or an unrecognized role value yields {} / drops
    that entry -- fail-closed, since minimum_role_for's default for an
    absent tool is "admin". `path` defaults to the package-resolved repo
    root's config/mcp_tool_roles.yaml; pass an explicit path (e.g. a
    tmp_path-scoped file) to override, such as in tests."""
    p = Path(path) if path is not None else _DEFAULT_PATH
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
