"""Tests for Orchestrator.execute_skill() and execute_skill_chain()."""
import asyncio
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Inject a stub 'anthropic' module so tests work without the real package.
# The stub is inserted BEFORE importing Orchestrator so that the lazy import
# inside execute_skill() resolves to our stub.
# ---------------------------------------------------------------------------
if "anthropic" not in sys.modules:
    _stub_anthropic = types.ModuleType("anthropic")
    _stub_anthropic.Anthropic = MagicMock()  # will be replaced per-test
    sys.modules["anthropic"] = _stub_anthropic

from promptwise_v2.core.orchestrator import Orchestrator
from promptwise_v2.core.skill_loader import Skill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(name="test_skill", model_tier="auto", output_schema=None, system_prompt=""):
    return Skill(
        name=name,
        description="A test skill",
        triggers=["test"],
        depends_on=[],
        output_schema=output_schema,
        roles=[],
        model_tier=model_tier,
        system_prompt=system_prompt,
        raw_content="",
    )


def _fake_anthropic_response(text="result text", model="claude-sonnet-4-6", input_tokens=100, output_tokens=50):
    """Build a minimal mock that looks like an anthropic Messages response."""
    resp = MagicMock()
    resp.model = model
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    return resp


# ---------------------------------------------------------------------------
# Test: no API key → returns error dict
# ---------------------------------------------------------------------------

def test_execute_skill_no_api_key():
    orc = Orchestrator()
    sk = _make_skill()
    # Ensure env var is absent
    env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        result = asyncio.get_event_loop().run_until_complete(
            orc.execute_skill(sk, {}, api_key=None)
        )
    assert result["status"] == "error"
    assert "ANTHROPIC_API_KEY not set" in result["error"]
    assert result["skill"] == "test_skill"


# ---------------------------------------------------------------------------
# Test: successful execution → proper dict shape
# ---------------------------------------------------------------------------

def test_execute_skill_success():
    orc = Orchestrator()
    sk = _make_skill()
    fake_resp = _fake_anthropic_response(text="skill output", input_tokens=200, output_tokens=80)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_resp

    with patch("anthropic.Anthropic", return_value=mock_client):
        result = asyncio.get_event_loop().run_until_complete(
            orc.execute_skill(sk, {"foo": "bar"}, api_key="test-key")
        )

    assert result["status"] == "success"
    assert result["skill"] == "test_skill"
    assert result["model_used"] == "claude-sonnet-4-6"
    assert result["result"] == "skill output"
    assert result["input_tokens"] == 200
    assert result["output_tokens"] == 80
    assert result["cost_usd"] == pytest.approx(200 * 0.000003 + 80 * 0.000015, rel=1e-6)


# ---------------------------------------------------------------------------
# Test: API exception → returns error dict
# ---------------------------------------------------------------------------

def test_execute_skill_api_exception():
    orc = Orchestrator()
    sk = _make_skill()
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("connection timeout")

    with patch("anthropic.Anthropic", return_value=mock_client):
        result = asyncio.get_event_loop().run_until_complete(
            orc.execute_skill(sk, {}, api_key="test-key")
        )

    assert result["status"] == "error"
    assert "connection timeout" in result["error"]
    assert result["skill"] == "test_skill"


# ---------------------------------------------------------------------------
# Test: router is used for model resolution
# ---------------------------------------------------------------------------

def test_execute_skill_uses_router():
    orc = Orchestrator()
    sk = _make_skill(name="code_review")
    fake_resp = _fake_anthropic_response(model="claude-opus-4-7")

    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_resp

    mock_router = MagicMock()
    mock_router.resolve_model.return_value = "claude-opus-4-7"

    with patch("anthropic.Anthropic", return_value=mock_client):
        result = asyncio.get_event_loop().run_until_complete(
            orc.execute_skill(sk, {}, api_key="test-key", router=mock_router, budget_pct=10.0)
        )

    mock_router.resolve_model.assert_called_once_with("code_review", 10.0)
    assert result["status"] == "success"
    assert result["model_used"] == "claude-opus-4-7"


# ---------------------------------------------------------------------------
# Test: model_tier is used when no router
# ---------------------------------------------------------------------------

def test_execute_skill_uses_model_tier():
    orc = Orchestrator()
    sk = _make_skill(model_tier="claude-haiku-4-5-20251001")
    fake_resp = _fake_anthropic_response(model="claude-haiku-4-5-20251001")

    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_resp

    with patch("anthropic.Anthropic", return_value=mock_client) as mock_anthropic:
        result = asyncio.get_event_loop().run_until_complete(
            orc.execute_skill(sk, {}, api_key="test-key")
        )

    # Verify the model passed to create()
    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs.kwargs.get("model") == "claude-haiku-4-5-20251001" or \
           (call_kwargs.args and call_kwargs.args[0] == "claude-haiku-4-5-20251001")
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Test: cache_control is set in system prompt block
# ---------------------------------------------------------------------------

def test_execute_skill_cache_control_present():
    orc = Orchestrator()
    sk = _make_skill()
    fake_resp = _fake_anthropic_response()

    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_resp

    with patch("anthropic.Anthropic", return_value=mock_client):
        asyncio.get_event_loop().run_until_complete(
            orc.execute_skill(sk, {}, api_key="test-key")
        )

    call_kwargs = mock_client.messages.create.call_args.kwargs
    system = call_kwargs.get("system", [])
    assert isinstance(system, list)
    assert len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}


# ---------------------------------------------------------------------------
# Test: execute_skill_chain with mocked execute_skill
# ---------------------------------------------------------------------------

def test_execute_skill_chain_success():
    orc = Orchestrator()

    sk_a = _make_skill(name="skill_a")
    sk_b = _make_skill(name="skill_b")

    # Create a minimal skill_loader mock
    skill_loader = MagicMock()
    def get_skill(name):
        return {"skill_a": sk_a, "skill_b": sk_b}.get(name)
    skill_loader.get_skill.side_effect = get_skill

    call_count = 0

    async def fake_execute_skill(skill, context, api_key=None, router=None, budget_pct=0.0):
        nonlocal call_count
        call_count += 1
        return {"status": "success", "skill": skill.name, "result": f"output_{skill.name}",
                "model_used": "claude-sonnet-4-6", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0}

    orc.execute_skill = fake_execute_skill

    result = asyncio.get_event_loop().run_until_complete(
        orc.execute_skill_chain(skill_loader, ["skill_a", "skill_b"], "sequential", {"ctx_key": "val"})
    )

    assert result["status"] == "completed"
    assert set(result["ordered_execution"]) == {"skill_a", "skill_b"}
    assert "skill_a" in result["results"]
    assert "skill_b" in result["results"]
    assert call_count == 2


def test_execute_skill_chain_stops_on_error():
    orc = Orchestrator()

    sk_a = _make_skill(name="skill_a")
    sk_b = _make_skill(name="skill_b")

    skill_loader = MagicMock()
    def get_skill(name):
        return {"skill_a": sk_a, "skill_b": sk_b}.get(name)
    skill_loader.get_skill.side_effect = get_skill

    async def fake_execute_skill(skill, context, api_key=None, router=None, budget_pct=0.0):
        if skill.name == "skill_a":
            return {"status": "error", "error": "API failure", "skill": skill.name}
        return {"status": "success", "skill": skill.name, "result": "ok",
                "model_used": "claude-sonnet-4-6", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0}

    orc.execute_skill = fake_execute_skill

    result = asyncio.get_event_loop().run_until_complete(
        orc.execute_skill_chain(skill_loader, ["skill_a", "skill_b"], "sequential", {})
    )

    assert result["status"] == "failed"
    assert "API failure" in result["error"]


# ---------------------------------------------------------------------------
# Test: _generate_mock_output is still accessible (backward compat)
# ---------------------------------------------------------------------------

def test_generate_mock_output_still_works():
    orc = Orchestrator()
    sk = _make_skill(output_schema={"type": "object", "properties": {"summary": {"type": "string"}}})
    out = orc._generate_mock_output(sk)
    assert "summary" in out
    assert out["summary"] == "mock_value"
