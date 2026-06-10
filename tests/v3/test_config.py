"""Tests for V3 config loader."""

from pathlib import Path
from promptwise_v3.config import load_config_v3, AppConfigV3


def test_load_config_defaults():
    cfg = load_config_v3(Path("."))
    assert isinstance(cfg, AppConfigV3)
    assert cfg.version == "3.0"
    assert cfg.default_model == "claude-sonnet-4-6"


def test_load_config_from_v3_yaml():
    cfg = load_config_v3(Path("config"))
    assert cfg.default_model == "claude-sonnet-4-6"
    assert len(cfg.models) >= 3


def test_config_has_providers():
    cfg = load_config_v3(Path("config"))
    assert len(cfg.providers) >= 1


def test_config_has_roles():
    cfg = load_config_v3(Path("config"))
    assert len(cfg.roles) >= 10


def test_config_policies():
    cfg = load_config_v3(Path("config"))
    assert cfg.policies.budget_hard_stop_usd == 10.0
    assert cfg.policies.max_tokens_per_session == 500000


def test_config_security():
    cfg = load_config_v3(Path("config"))
    assert cfg.security.pii_detection is True
    assert cfg.security.pii_action == "redact"


def test_config_dashboard():
    cfg = load_config_v3(Path("config"))
    assert cfg.dashboard.web_port == 8765
    assert cfg.dashboard.web_enabled is True


def test_config_skills():
    cfg = load_config_v3(Path("config"))
    assert cfg.skills.directory == "skills/"
    assert cfg.skills.chain_mode == "sequential"


def test_config_get_model():
    cfg = load_config_v3(Path("config"))
    m = cfg.get_model("claude-sonnet-4-6")
    assert m.provider == "claude"
    assert m.rates.input_per_mtok == 3.0
