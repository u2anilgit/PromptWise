"""tests.test_config -- per-section config loading tests.

New file (WP1 Task 8): tests/test_config.py did not previously exist in this
codebase. Style mirrors config.py's own SecurityConfig/sec_raw wiring
pattern -- write a promptwise.yaml into a tmp dir and load it via
load_config(), asserting the resulting dataclass fields.
"""
from pathlib import Path

from promptwise.config import AuditConfig, load_config


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
