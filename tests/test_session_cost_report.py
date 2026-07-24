"""Session-level cost rollup -- see
docs/superpowers/specs/2026-07-24-three-quick-wins-design.md.
"""
import pytest

from promptwise.core.session_context import CURRENT_SESSION_ID
from promptwise.db.models import MemoryManager


def test_current_session_id_is_stable_nonempty_string():
    assert isinstance(CURRENT_SESSION_ID, str)
    assert len(CURRENT_SESSION_ID) > 0
    from promptwise.core import session_context
    assert session_context.CURRENT_SESSION_ID == CURRENT_SESSION_ID


@pytest.mark.asyncio
async def test_session_cost_report_groups_by_session(tmp_path):
    mem = MemoryManager(str(tmp_path / "mem.db"))
    await mem.init()
    await mem.record_cost(session_id="s1", tool="route_request", model="claude-sonnet-4-6", cost_usd=0.01)
    await mem.record_cost(session_id="s1", tool="rewrite_prompt", model="claude-sonnet-4-6", cost_usd=0.02)
    await mem.record_cost(session_id="s2", tool="route_request", model="claude-haiku-4-5-20251001", cost_usd=0.005)

    rows = await mem.session_cost_report()
    by_id = {r["session_id"]: r for r in rows}
    assert by_id["s1"]["calls"] == 2
    assert round(by_id["s1"]["total_cost_usd"], 6) == 0.03
    assert by_id["s1"]["by_tool"] == {"route_request": 1, "rewrite_prompt": 1}
    assert by_id["s2"]["calls"] == 1
    assert round(by_id["s2"]["total_cost_usd"], 6) == 0.005


@pytest.mark.asyncio
async def test_session_cost_report_since_filter(tmp_path):
    mem = MemoryManager(str(tmp_path / "mem.db"))
    await mem.init()
    await mem.record_cost(session_id="s1", tool="route_request", model="m", cost_usd=0.01)
    rows_all = await mem.session_cost_report()
    rows_future = await mem.session_cost_report(since="2099-01-01T00:00:00")
    assert len(rows_all) == 1
    assert rows_future == []


@pytest.mark.asyncio
async def test_session_cost_report_empty_db_returns_empty_list(tmp_path):
    mem = MemoryManager(str(tmp_path / "mem.db"))
    await mem.init()
    assert await mem.session_cost_report() == []


@pytest.mark.asyncio
async def test_session_cost_report_sorted_newest_last_ts_first(tmp_path):
    mem = MemoryManager(str(tmp_path / "mem.db"))
    await mem.init()
    await mem.record_cost(session_id="old", tool="t", model="m", cost_usd=0.0)
    await mem.record_cost(session_id="new", tool="t", model="m", cost_usd=0.0)
    rows = await mem.session_cost_report()
    assert rows[0]["session_id"] == "new"
    assert rows[1]["session_id"] == "old"
