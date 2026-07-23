"""Task 5 (P1) — opt-in hard-blocking budget mode.

Advisory-by-default is a stated project identity: BudgetGuardian must never
block spend unless a caller explicitly opts in via mode="block". Default
behavior (existing callers, existing tests) must be unchanged.
"""
import asyncio
import json
import typing

import pytest

from promptwise.plugins.budget import BudgetGuardian
from promptwise import server as srv


def test_default_mode_is_advise_and_never_blocks():
    g = BudgetGuardian(limit_usd=10.0)
    assert g.mode == "advise"
    status = g.check(used_usd=100.0, days_elapsed=1)
    assert status.alert_level == "hard_stop"
    assert status.blocked is False


def test_block_mode_marks_over_limit_spend_as_blocked():
    g = BudgetGuardian(limit_usd=10.0)
    g.set_mode("block")
    status = g.check(used_usd=100.0, days_elapsed=1)
    assert status.alert_level == "hard_stop"
    assert status.blocked is True


def test_block_mode_does_not_block_under_limit_spend():
    g = BudgetGuardian(limit_usd=10.0)
    g.set_mode("block")
    status = g.check(used_usd=1.0, days_elapsed=1)
    assert status.blocked is False


def test_set_mode_rejects_unknown_mode():
    g = BudgetGuardian(limit_usd=10.0)
    with pytest.raises(ValueError):
        g.set_mode("deny-everything")


class _Ctx:
    def __init__(self, budget):
        self.budget = budget


def _call(name, arguments, ctx):
    coro = typing.cast(
        "typing.Coroutine[typing.Any, typing.Any, str]",
        srv._HANDLERS[name](typing.cast(srv.ServerContext, ctx), arguments),
    )
    return asyncio.run(coro)


def test_set_budget_limit_handler_accepts_mode_and_flips_guardian():
    ctx = _Ctx(BudgetGuardian(limit_usd=10.0))
    out = json.loads(_call("set_budget_limit", {"limit_usd": 5.0, "mode": "block"}, ctx))
    assert out["mode"] == "block"
    assert ctx.budget.mode == "block"


def test_monitor_budget_handler_advisory_mode_returns_normal_json():
    ctx = _Ctx(BudgetGuardian(limit_usd=10.0))
    out = json.loads(_call("monitor_budget", {"used_usd": 100.0}, ctx))
    assert out["alert_level"] == "hard_stop"
    assert out["blocked"] is False
    assert "error" not in out


def test_monitor_budget_handler_block_mode_surfaces_hard_error():
    ctx = _Ctx(BudgetGuardian(limit_usd=10.0))
    ctx.budget.set_mode("block")
    out = json.loads(_call("monitor_budget", {"used_usd": 100.0}, ctx))
    assert out["type"] == "BudgetExceededError"
    assert out["blocked"] is True
