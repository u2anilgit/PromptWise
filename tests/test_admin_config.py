from promptwise.core.admin_config import load_admin_config, set_feature_flag, get_admin_settings


def test_missing_config_file_returns_defaults(tmp_path):
    cfg = load_admin_config(tmp_path / "admin.yaml")
    assert cfg["features"] == {}
    assert cfg["knowledgebase"]["enabled"] is False


def test_set_feature_flag_global(tmp_path):
    path = tmp_path / "admin.yaml"
    set_feature_flag("knowledgebase.enabled", True, path=path)

    settings = get_admin_settings(path=path)
    assert settings["features"]["knowledgebase.enabled"] is True


def test_set_feature_flag_project_scoped(tmp_path):
    path = tmp_path / "admin.yaml"
    set_feature_flag("knowledgebase.enabled", True, project="team-a", path=path)

    settings = get_admin_settings(path=path)
    assert settings["project_features"]["team-a"]["knowledgebase.enabled"] is True
    # global default untouched
    assert settings["features"].get("knowledgebase.enabled") is not True


def test_set_feature_flag_persists_across_loads(tmp_path):
    path = tmp_path / "admin.yaml"
    set_feature_flag("some.flag", True, path=path)

    reloaded = load_admin_config(path)
    assert reloaded["features"]["some.flag"] is True
