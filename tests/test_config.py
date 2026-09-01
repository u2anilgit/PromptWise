"""tests.test_config -- per-section config loading tests.

New file (WP1 Task 8): tests/test_config.py did not previously exist in this
codebase. Style mirrors config.py's own SecurityConfig/sec_raw wiring
pattern -- write a promptwise.yaml into a tmp dir and load it via
load_config(), asserting the resulting dataclass fields.
"""
from pathlib import Path

from promptwise.config import AuditConfig, DetectionConfig, load_config


def _write_yaml(tmp_path: Path, text: str) -> Path:
    (tmp_path / "promptwise.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def test_audit_config_defaults_when_no_audit_key(tmp_path):
    _write_yaml(tmp_path, "version: '1.0'\n")
    cfg = load_config(tmp_path)
    assert cfg.audit.retention_days == 0
    assert cfg.audit.capture_prompts is False


def test_audit_config_overrides_from_yaml(tmp_path):
    _write_yaml(
        tmp_path,
        "version: '1.0'\naudit:\n  retention_days: 90\n  capture_prompts: true\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.audit.retention_days == 90
    assert cfg.audit.capture_prompts is True


def test_audit_config_dataclass_defaults():
    ac = AuditConfig()
    assert ac.retention_days == 0
    assert ac.capture_prompts is False


def test_detection_config_defaults_when_no_detection_key(tmp_path):
    _write_yaml(tmp_path, "version: '1.0'\n")
    cfg = load_config(tmp_path)
    assert cfg.detection.mad_threshold == 3.0
    assert cfg.detection.alert_on_findings is False
    assert cfg.detection.siem_mode == "file"


def test_detection_config_overrides_from_yaml(tmp_path):
    _write_yaml(
        tmp_path,
        "version: '1.0'\ndetection:\n  mad_threshold: 2.5\n  alert_on_findings: true\n  siem_mode: webhook\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.detection.mad_threshold == 2.5
    assert cfg.detection.alert_on_findings is True
    assert cfg.detection.siem_mode == "webhook"


def test_detection_config_dataclass_defaults():
    dc = DetectionConfig()
    assert dc.mad_threshold == 3.0
    assert dc.alert_on_findings is False
    assert dc.siem_mode == "file"


def test_identity_config_defaults_are_empty_strings():
    from promptwise.config import AppConfig, IdentityConfig

    cfg = AppConfig()
    assert cfg.identity == IdentityConfig(ldap_server="", ldap_search_base="", db_url="")


def test_identity_config_loaded_from_yaml(tmp_path):
    from promptwise.config import load_config

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "promptwise.yaml").write_text(
        "identity:\n"
        "  ldap_server: \"ldaps://dc.corp.local\"\n"
        "  ldap_search_base: \"dc=corp,dc=local\"\n"
        "  db_url: \"postgresql+asyncpg://user:pass@host/promptwise\"\n",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert cfg.identity.ldap_server == "ldaps://dc.corp.local"
    assert cfg.identity.ldap_search_base == "dc=corp,dc=local"
    assert cfg.identity.db_url == "postgresql+asyncpg://user:pass@host/promptwise"


def test_identity_db_url_env_var_overrides_yaml(tmp_path, monkeypatch):
    from promptwise.config import load_config

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "promptwise.yaml").write_text(
        "identity:\n"
        "  db_url: \"postgresql+asyncpg://user:pass@host/promptwise\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROMPTWISE_DB_URL", "postgresql+asyncpg://envuser:envpass@envhost/promptwise")
    cfg = load_config(tmp_path)
    assert cfg.identity.db_url == "postgresql+asyncpg://envuser:envpass@envhost/promptwise"
