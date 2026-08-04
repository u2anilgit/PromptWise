"""Phase 14 WP14.3 -- workflow-level cost attribution.

``BudgetGuardian.check()`` previously only ever saw one aggregate ``used_usd``
figure -- no way to see how much of a workflow's spend was LLM token cost vs.
tool/API execution cost (LangSmith attributes both; see
``docs/GAP_ANALYSIS_2026-07.md`` section 5). ``check()`` now accepts an optional
``tool_cost_usd`` leg that is added to the LLM leg for limit/alert/burn-rate
purposes and surfaced as a ``cost_breakdown`` on ``BudgetStatus`` -- purely
additive: every existing caller (the ``monitor_budget`` MCP tool,
``dashboard/web.py``) that never passes ``tool_cost_usd`` sees byte-for-byte
identical behavior.
"""
import asyncio
import json
import typing

import promptwise.server as s
from promptwise.plugins.budget import BudgetGuardian


def test_check_without_tool_cost_is_unchanged():
    g = BudgetGuardian(limit_usd=10.0)
    r = g.check(used_usd=5.0, days_elapsed=1)
    assert r.used_usd == 5.0
    assert r.cost_breakdown is None


def test_check_attributes_tool_cost_alongside_llm_cost():
    g = BudgetGuardian(limit_usd=10.0)
    r = g.check(used_usd=3.0, days_elapsed=1, tool_cost_usd=2.0)
    assert r.used_usd == 5.0  # total (LLM + tool)
    assert r.cost_breakdown == {"llm_usd": 3.0, "tool_usd": 2.0}


def test_tool_cost_counts_toward_hard_stop():
    g = BudgetGuardian(limit_usd=10.0)
    # LLM spend alone is under the limit; LLM + tool spend crosses it.
    r = g.check(used_usd=6.0, days_elapsed=1, tool_cost_usd=5.0)
    assert r.alert_level == "hard_stop"


def test_tool_cost_counts_toward_daily_burn_and_projection():
    g = BudgetGuardian(limit_usd=100.0)
    r = g.check(used_usd=1.0, days_elapsed=1, tool_cost_usd=1.0)
    assert r.daily_burn_usd == 2.0
    assert r.projected_monthly_usd == 60.0


def test_zero_tool_cost_explicit_is_same_as_omitted():
    g = BudgetGuardian(limit_usd=10.0)
    r = g.check(used_usd=4.0, days_elapsed=1, tool_cost_usd=0.0)
    assert r.used_usd == 4.0
    assert r.cost_breakdown is None


# ── MCP tool surface: monitor_budget wires tool_cost_usd through ────────────
def test_monitor_budget_tool_schema_has_tool_cost_param():
    tool = next(t for t in s._TOOL_DEFS if t.name == "monitor_budget")
    assert "tool_cost_usd" in tool.inputSchema["properties"]


def test_monitor_budget_handler_surfaces_cost_breakdown():
    class _FakeCtx:
        budget = BudgetGuardian(limit_usd=10.0)

    # _FakeCtx only carries .budget, the only attr _handle_monitor_budget reads;
    # cast documents the deliberate shortfall against the full ServerContext.
    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = asyncio.run(s._handle_monitor_budget(ctx, {"used_usd": 3.0, "tool_cost_usd": 2.0}))
    body = json.loads(out)
    assert body["cost_breakdown"] == {"llm_usd": 3.0, "tool_usd": 2.0}
    assert body["used_usd"] == 5.0


def test_monitor_budget_handler_backward_compatible_without_tool_cost():
    class _FakeCtx:
        budget = BudgetGuardian(limit_usd=10.0)

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = asyncio.run(s._handle_monitor_budget(ctx, {"used_usd": 3.0}))
    body = json.loads(out)
    assert body["cost_breakdown"] is None
    assert body["used_usd"] == 3.0
