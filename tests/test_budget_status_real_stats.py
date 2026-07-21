"""get_budget_status used to always return current_spend_usd: 0.0 --
BudgetGuardian._current_spend/_daily_burn were set once in __init__ and never
written anywhere. It must instead read real cost_logs via
ctx.memory.raw_cost_logs (month-to-date), the same source budget_report
already reads.
"""
import asyncio
import json
import typing

import promptwise.server as s
from promptwise.plugins.budget import BudgetGuardian


class _FakeMemory:
    def __init__(self, rows):
        self._rows = rows

    async def raw_cost_logs(self, since=None):
        return self._rows


def _row(day: str, cost: float) -> dict:
    return {"ts": f"{day}T00:00:00+00:00", "cost_usd": cost}


def test_get_budget_status_reflects_real_cost_logs():
    class _FakeCtx:
        budget = BudgetGuardian(limit_usd=10.0)
        memory = _FakeMemory([_row("2026-07-01", 1.0), _row("2026-07-02", 2.0)])

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = asyncio.run(s._handle_get_budget_status(ctx, {}))
    body = json.loads(out)
    assert body["current_spend_usd"] == 3.0
    assert body["pct_used"] == 30.0


def test_get_budget_status_no_logs_yields_zero_not_fake_data():
    class _FakeCtx:
        budget = BudgetGuardian(limit_usd=10.0)
        memory = _FakeMemory([])

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = asyncio.run(s._handle_get_budget_status(ctx, {}))
    body = json.loads(out)
    assert body["current_spend_usd"] == 0.0
    assert body["days_remaining_at_burn_rate"] is None


def test_budget_guardian_get_budget_status_default_backward_compatible():
    g = BudgetGuardian(limit_usd=10.0)
    status = g.get_budget_status()
    assert status["current_spend_usd"] == 0.0
