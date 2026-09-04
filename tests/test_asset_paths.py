"""Regression coverage for source, editable, and packaged asset discovery."""
from promptwise.asset_paths import (
    PACKAGE_ASSET_ROOT,
    resolve_asset,
    resolve_config_dir,
    resolve_skill_dir,
)
from promptwise.config import load_config
from promptwise.core.skill_loader import SkillLoader


def test_packaged_runtime_assets_exist():
    assert (PACKAGE_ASSET_ROOT / "config" / "promptwise.yaml").is_file()
    assert (PACKAGE_ASSET_ROOT / "skill_packs").is_dir()
    assert (PACKAGE_ASSET_ROOT / "corpus" / "injection_corpus.json").is_file()


def test_default_discovery_works_from_arbitrary_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_dir = resolve_config_dir()
    skill_dir = resolve_skill_dir()
    assert (config_dir / "promptwise.yaml").is_file()
    assert skill_dir.is_dir()
    assert load_config().models

    loader = SkillLoader()
    loader.load_skills()
    assert len(loader.skills) >= 80


def test_explicit_root_overrides_packaged_asset(tmp_path):
    marker = tmp_path / "config" / "custom.yaml"
    marker.parent.mkdir()
    marker.write_text("custom", encoding="utf-8")
    assert resolve_asset("config/custom.yaml", root=tmp_path) == marker


def test_explicit_config_directory_remains_supported(tmp_path):
    (tmp_path / "promptwise.yaml").write_text("version: 'test'\n", encoding="utf-8")
    assert load_config(tmp_path).version == "test"
