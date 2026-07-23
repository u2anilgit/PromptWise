"""handlers/ package split -- fault isolation. A single handler category
failing to import must not crash server startup or affect any other
category's tools being present in the registry; the failure must be
visible (recorded in _HANDLER_LOAD_ERRORS), not silently swallowed."""
import importlib
import sys

import promptwise.server as server


def test_broken_category_does_not_crash_others(monkeypatch):
    # Simulate a category whose import raises -- e.g. a bad dependency or a
    # syntax error a future contributor introduces.
    real_import_module = importlib.import_module

    def _boom(name, *a, **k):
        if name == "promptwise.handlers.code_validation":
            raise ImportError("simulated broken category")
        return real_import_module(name, *a, **k)

    monkeypatch.setattr(server.importlib, "import_module", _boom)
    monkeypatch.setattr(server, "_HANDLER_LOAD_ERRORS", {})

    # Re-run the loader with the patched import -- does not raise.
    server._load_handler_modules()

    assert "code_validation" in server._HANDLER_LOAD_ERRORS
    assert "simulated broken category" in server._HANDLER_LOAD_ERRORS["code_validation"]


def test_broken_category_is_visible_not_swallowed(monkeypatch):
    monkeypatch.setattr(server, "_HANDLER_LOAD_ERRORS", {})
    real_import_module = importlib.import_module

    def _boom(name, *a, **k):
        if name.endswith(".code_validation"):
            raise RuntimeError("disk exploded")
        return real_import_module(name, *a, **k)

    monkeypatch.setattr(server.importlib, "import_module", _boom)
    server._load_handler_modules()

    assert server._HANDLER_LOAD_ERRORS.get("code_validation") == "RuntimeError: disk exploded"


def test_other_categories_still_present_after_isolated_failure():
    # After the two tests above intentionally broke code_validation's live
    # import path via monkeypatch (reverted on teardown), a fresh, real
    # load must still succeed for every category currently in
    # _HANDLER_MODULES -- confirms the mechanism itself (not just the
    # simulated failure) doesn't leak state across categories.
    server._HANDLER_LOAD_ERRORS.clear()
    server._load_handler_modules()
    assert server._HANDLER_LOAD_ERRORS == {}
    for module_name in server._HANDLER_MODULES:
        mod = sys.modules.get(f"promptwise.handlers.{module_name}")
        assert mod is not None, f"{module_name} should have imported cleanly"
