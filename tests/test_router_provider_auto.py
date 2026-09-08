import pytest

from promptwise.core import host_detector
from promptwise.core.router import Router

_ENV_VARS = ("PROMPTWISE_HOST", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CURSOR_TRACE_ID",
             "CODEX_SANDBOX", "CODEX_HOME", "GEMINI_CLI", "GEMINI_SYSTEM_MD")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    host_detector.set_client_info(None)
    yield
    host_detector.set_client_info(None)


def test_provider_auto_resolves_from_the_detected_host(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_HOST", "gemini")
    r = Router().route(text="write a function", provider="auto")
    assert r.provider_used == "gemini"
    assert r.host_detected == "gemini"


def test_explicit_provider_still_wins_over_detection(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_HOST", "gemini")
    r = Router().route(text="write a function", provider="claude")
    assert r.provider_used == "claude"
    assert r.host_detected == ""


def test_default_provider_argument_is_unchanged_for_existing_callers():
    """Every existing call site passes provider='claude' or omits it; the
    omitted case must keep meaning 'claude', not silently become 'auto'."""
    r = Router().route(text="write a function")
    assert r.provider_used == "claude"


def test_auto_routing_picks_a_model_the_host_can_actually_call(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_HOST", "gemini")
    r = Router().route(text="refactor this module for clarity", provider="auto")
    assert r.recommended_model, "auto routing produced no model"
    reg = Router().registry
    provider = reg.provider_of(r.recommended_model)
    # An unknown provider means the alias came from the config fallback rather
    # than the registry; the assertion is that it is never another provider's.
    assert provider in ("gemini", "")


def test_preflight_uses_the_detected_host(monkeypatch):
    from promptwise.core.preflight import run_preflight
    monkeypatch.setenv("PROMPTWISE_HOST", "gemini")
    res = run_preflight("Design and implement a distributed rate limiter for production traffic.")
    assert res.task_type
    # cross-provider advisory compares model provider to host provider; with the
    # host resolved they now agree, so no spurious "different provider" note
    assert not res.cross_provider_suggested or "gemini" not in res.cross_provider_note
