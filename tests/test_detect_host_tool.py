import json

import pytest

from promptwise.core import host_detector

_ENV_VARS = ("PROMPTWISE_HOST", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CURSOR_TRACE_ID",
             "CODEX_SANDBOX", "CODEX_HOME", "GEMINI_CLI", "GEMINI_SYSTEM_MD")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    host_detector.set_client_info(None)
    yield
    host_detector.set_client_info(None)


def test_detect_host_is_registered_as_a_tool():
    import promptwise.server as s
    assert any(t.name == "detect_host" for t in s._TOOL_DEFS)


@pytest.mark.asyncio
async def test_detect_host_tool_reports_host_and_routable_models(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_HOST", "claude")
    from promptwise.handlers.detection import _handle_detect_host
    out = json.loads(await _handle_detect_host(None, {}))
    assert out["host"] == "claude"
    assert out["provider"] == "claude"
    assert out["confidence"] == 1.0
    assert isinstance(out["models_available"], list)
    assert out["models_available"], "a detected host with no routable model is not actionable"


@pytest.mark.asyncio
async def test_detect_host_only_offers_models_the_host_can_call(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_HOST", "gemini")
    from promptwise.core.model_registry import ModelRegistry
    from promptwise.handlers.detection import _handle_detect_host
    out = json.loads(await _handle_detect_host(None, {}))
    assert out["provider"] == "gemini"
    reg = ModelRegistry()
    for alias in out["models_available"]:
        assert reg.provider_of(alias) == "gemini", alias


@pytest.mark.asyncio
async def test_route_request_reports_the_host_it_routed_for(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_HOST", "claude")
    import promptwise.server as s
    ctx = await s._build_context()
    out = json.loads(await s.call_tool(ctx, "route_request", {"text": "write a parser"}))
    assert out["host_detected"] == "claude"
    assert out["provider_used"] == "claude"
    assert out["effort_param"], "the effort parameter should be resolved for the routed provider"
