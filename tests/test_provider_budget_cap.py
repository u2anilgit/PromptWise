"""Phase 14 WP14.2 -- provider-level hard budget cap at routing time.

Mirrors LiteLLM's ``provider_budget_routing`` pattern (see
``docs/GAP_ANALYSIS_2026-07.md`` section 5): once a provider's configured cap is
hit, routing itself refuses the requested tier and reroutes to the cheapest
("fast") tier BEFORE a call is made -- not just reported after the fact by
``BudgetGuardian``. ``provider_spend_usd`` is caller-supplied, mirroring the
existing caller-supplied ``monthly_budget_usd``/``days_elapsed_in_month``
convention already on ``Router.route()`` -- Router owns no spend persistence of
its own. No cap configured (the default) means no behavior change at all.
"""
import asyncio
import json
import typing

import promptwise.server as s
from promptwise.config import AppConfig, ProviderConfig
from promptwise.core.router import Router


def _config_with_cap(cap):
    cfg = AppConfig()
    cfg.providers["claude"] = ProviderConfig(
        display_name="Claude", aliases=["anthropic"],
        fast="claude-haiku-4-5-20251001", balanced="claude-sonnet-4-6", powerful="claude-opus-4-7",
        daily_cap_usd=cap,
    )
    return cfg


def test_no_cap_configured_never_caps():
    r = Router(AppConfig())
    res = r.route("write a function", intent="code", stakes="high", provider="claude",
                  provider_spend_usd=999.0)
    assert res.provider_capped is False


def test_spend_under_cap_routes_normally():
    r = Router(_config_with_cap(50.0))
    res = r.route("write a function", intent="code", stakes="high", provider="claude",
                  provider_spend_usd=10.0)
    assert res.provider_capped is False


def test_spend_at_cap_reroutes_to_fast_tier():
    r = Router(_config_with_cap(50.0))
    res = r.route("Design a critical production security architecture", intent="analysis",
                  stakes="high", provider="claude", provider_spend_usd=50.0)
    assert res.provider_capped is True
    assert res.recommended_model == "claude-haiku-4-5-20251001"
    assert "budget cap" in res.reason.lower()


def test_spend_over_cap_reroutes_to_fast_tier():
    r = Router(_config_with_cap(50.0))
    res = r.route("Design a critical production security architecture", intent="analysis",
                  stakes="high", provider="claude", provider_spend_usd=75.0)
    assert res.provider_capped is True
    assert res.recommended_model == "claude-haiku-4-5-20251001"


def test_no_provider_spend_supplied_never_caps_fail_open():
    r = Router(_config_with_cap(0.01))  # trivially tiny cap
    res = r.route("write a function", intent="code", stakes="high", provider="claude")
    assert res.provider_capped is False


def test_cap_enforcement_is_per_provider_not_global():
    r = Router(_config_with_cap(1.0))
    res = r.route("write a function", intent="code", stakes="high", provider="codex",
                  provider_spend_usd=999.0)
    assert res.provider_capped is False


# ── MCP tool surface: route_request wires provider_spend_usd through ────────
def test_route_request_tool_schema_has_provider_spend_param():
    tool = next(t for t in s._TOOL_DEFS if t.name == "route_request")
    assert "provider_spend_usd" in tool.inputSchema["properties"]


class _FakeMemory:
    async def record_cost(self, **kwargs):
        return None


class _FakeCtx:
    def __init__(self, budget=None, router=None):
        self.budget = budget
        self.router = router
        self.memory = _FakeMemory()


def test_route_request_handler_surfaces_provider_capped():
    # _FakeCtx only carries the attrs _handle_route_request reads (router/
    # budget/memory); cast documents the deliberate shortfall against the
    # full ServerContext instead of building a real 23-field one.
    ctx = typing.cast(s.ServerContext, _FakeCtx(router=Router(_config_with_cap(1.0))))
    out = asyncio.run(s._handle_route_request(ctx, {
        "text": "write a function", "intent": "code", "stakes": "high",
        "provider": "claude", "provider_spend_usd": 5.0}))
    body = json.loads(out)
    assert body["provider_capped"] is True
    assert body["recommended_model"] == "claude-haiku-4-5-20251001"
