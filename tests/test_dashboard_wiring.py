"""cli.py's _start_serve used to call create_web_app(cfg) -- filling the
stats_service param with the wrong type and never passing memory_manager at
all, so the web dashboard always read as empty regardless of real cost_logs.
_do_stats and the CLI-only serve path had the same problem via
guardian.get_budget_status() with no real spend fed in. This locks in real
data flowing through both paths via isolated (tmp_path) databases.
"""
import asyncio

from promptwise.cli import _memory_manager, _real_budget_status
from promptwise.plugins.budget import BudgetGuardian


def test_memory_manager_is_initialized_and_queryable(tmp_path):
    db_path = str(tmp_path / "mem.db")
    mm = asyncio.run(_memory_manager(db_path))
    logs = asyncio.run(mm.raw_cost_logs(since="1970-01-01T00:00:00+00:00"))
    assert isinstance(logs, list)


def test_real_budget_status_reflects_seeded_spend(tmp_path):
    db_path = str(tmp_path / "mem.db")
    mm = asyncio.run(_memory_manager(db_path))
    asyncio.run(mm.record_cost(tool="route_request", session_id="s1", model="m", cost_usd=4.0))

    guardian = BudgetGuardian(limit_usd=10.0)
    status = asyncio.run(_real_budget_status(guardian, db_path))
    assert status["current_spend_usd"] == 4.0
    assert status["pct_used"] == 40.0


def test_real_budget_status_no_spend_yields_zero(tmp_path):
    db_path = str(tmp_path / "mem.db")
    asyncio.run(_memory_manager(db_path))  # creates the (empty) DB

    guardian = BudgetGuardian(limit_usd=10.0)
    status = asyncio.run(_real_budget_status(guardian, db_path))
    assert status["current_spend_usd"] == 0.0
