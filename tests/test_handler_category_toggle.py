"""handlers/ package split -- category enable/disable toggle. Config- and
env-driven, filtered before the import loop runs. Default (nothing
configured) must leave every category enabled -- this is an opt-in
restriction, never an opt-in requirement."""
import importlib

import promptwise.server as server


def test_default_leaves_all_categories_enabled(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_DISABLED_HANDLER_CATEGORIES", raising=False)
    assert server._disabled_categories() == set()


def test_env_var_disables_a_category(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_DISABLED_HANDLER_CATEGORIES", "code_validation, agile")
    assert server._disabled_categories() == {"code_validation", "agile"}


def test_config_and_env_are_unioned(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_DISABLED_HANDLER_CATEGORIES", "agile")

    class _FakeHandlersConfig:
        disabled_categories = ["security"]

    class _FakeConfig:
        handlers = _FakeHandlersConfig()

    monkeypatch.setattr(
        "promptwise.config.load_config", lambda *a, **k: _FakeConfig()
    )
    assert server._disabled_categories() == {"agile", "security"}
