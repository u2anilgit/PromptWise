import os
from pathlib import Path

from promptwise.core import admin_config
from promptwise.core.admin_config import load_admin_config, set_feature_flag, get_admin_settings


def test_default_path_is_package_root_relative_not_cwd(tmp_path, monkeypatch):
    """_DEFAULT_PATH must resolve from the package root (like doctor.py/
    hook_bridge.py/model_registry.py/effort_map.py), never from the process's
    current working directory -- finding #1."""
    expected = Path(admin_config.__file__).resolve().parents[3] / "config" / "admin.yaml"
    assert admin_config._DEFAULT_PATH == expected

    monkeypatch.chdir(tmp_path)
    # Re-resolving from a fresh cwd must not change the module-level constant.
    assert admin_config._DEFAULT_PATH == expected
    assert admin_config._DEFAULT_PATH != Path("config") / "admin.yaml"


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
