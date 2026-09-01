# tests/test_tool_rbac.py
from promptwise.core.tool_rbac import load_tool_roles, minimum_role_for


def test_load_tool_roles_missing_file_returns_empty_dict(tmp_path):
    assert load_tool_roles(str(tmp_path / "does_not_exist.yaml")) == {}


def test_load_tool_roles_reads_entries(tmp_path):
    p = tmp_path / "mcp_tool_roles.yaml"
    p.write_text("tool_roles:\n  list_tasks: viewer\n  set_feature_flag: admin\n", encoding="utf-8")
    assert load_tool_roles(str(p)) == {"list_tasks": "viewer", "set_feature_flag": "admin"}


def test_load_tool_roles_drops_entries_with_invalid_role(tmp_path):
    p = tmp_path / "mcp_tool_roles.yaml"
    p.write_text("tool_roles:\n  good_tool: admin\n  bad_tool: superuser\n", encoding="utf-8")
    assert load_tool_roles(str(p)) == {"good_tool": "admin"}


def test_load_tool_roles_malformed_yaml_returns_empty_dict(tmp_path):
    p = tmp_path / "mcp_tool_roles.yaml"
    p.write_text("tool_roles: [this is not\n  a valid: mapping", encoding="utf-8")
    assert load_tool_roles(str(p)) == {}


def test_minimum_role_for_known_tool_returns_mapped_role():
    tool_roles = {"list_tasks": "viewer", "set_feature_flag": "admin"}
    assert minimum_role_for("list_tasks", tool_roles) == "viewer"


def test_minimum_role_for_unknown_tool_defaults_to_admin():
    tool_roles = {"list_tasks": "viewer"}
    assert minimum_role_for("some_future_tool_never_classified", tool_roles) == "admin"


def test_minimum_role_for_empty_map_defaults_every_tool_to_admin():
    assert minimum_role_for("list_tasks", {}) == "admin"


def test_real_config_file_loads_and_classifies_correctly():
    """The actual shipped config/mcp_tool_roles.yaml -- confirms it parses
    and a handful of known entries land where the design doc says."""
    tool_roles = load_tool_roles("config/mcp_tool_roles.yaml")
    assert tool_roles["list_tasks"] == "viewer"
    assert tool_roles["set_feature_flag"] == "admin"
    assert tool_roles["get_admin_settings"] == "admin"  # manual override -- see design doc
    assert tool_roles["query_audit"] == "viewer"
    assert tool_roles["run_governor"] == "admin"


def test_export_org_report_is_admin_only():
    """export_org_report writes to an operator-supplied out_path with no
    path validation (core/report_export.py's write_report()) -- it must
    never regress back to viewer, which would let a remote viewer token
    overwrite arbitrary files the server process can write to."""
    tool_roles = load_tool_roles("config/mcp_tool_roles.yaml")
    assert minimum_role_for("export_org_report", tool_roles) == "admin"


def test_default_path_resolves_from_package_location_not_cwd(tmp_path, monkeypatch):
    """load_tool_roles() with no argument must find the real repo-root
    config/mcp_tool_roles.yaml regardless of the process's cwd -- a
    cwd-relative default would silently load {} (and thus fail-closed
    admin-only for every tool) for any deployment not launched from the
    repo root."""
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / "config").exists()  # confirm cwd has no config/ at all
    tool_roles = load_tool_roles()
    assert tool_roles["list_tasks"] == "viewer"
