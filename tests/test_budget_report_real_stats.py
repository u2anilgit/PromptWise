"""``budget_report`` used to return a hardcoded fake cost series on every call,
regardless of period/project or actual spend (see server.py history). It must
instead read real cost_logs via ``ctx.memory.raw_cost_logs`` and derive a real
daily-cost series and total.
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
    return {"ts": f"{day}T00:00:00+00:00", "session_id": "s1", "tool": "t",
            "model": "m", "input_tokens": 0, "output_tokens": 0,
            "cost_usd": cost, "saving_pct": 0, "lines": 0}


def test_budget_report_reflects_real_cost_logs():
    class _FakeCtx:
        budget = BudgetGuardian(limit_usd=10.0)
        memory = _FakeMemory([_row("2026-07-10", 1.0), _row("2026-07-10", 0.5), _row("2026-07-11", 2.0)])

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = asyncio.run(s._handle_budget_report(ctx, {"period": "weekly"}))
    body = json.loads(out)
    assert body["total_cost_usd"] == 3.5
    assert body["anomaly"]["latest"] == 2.0


def test_budget_report_no_logs_yields_zero_not_fake_data():
    class _FakeCtx:
        budget = BudgetGuardian(limit_usd=10.0)
        memory = _FakeMemory([])

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = asyncio.run(s._handle_budget_report(ctx, {"period": "daily"}))
    body = json.loads(out)
    assert body["total_cost_usd"] == 0.0
    assert body["anomaly"]["reason"] == "No data"
