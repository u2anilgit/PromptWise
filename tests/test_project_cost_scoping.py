"""Per-project cost scoping -- see
docs/superpowers/specs/2026-08-03-preflight-pipeline-design.md §3.
"""
import pytest

from promptwise.db.models import MemoryManager


@pytest.mark.asyncio
async def test_project_id_column_added_via_migration_on_existing_db(tmp_path):
    # Simulate a pre-migration DB: init once (creates schema incl. project_id
    # since it's new), then init again on the same path -- the ALTER TABLE
    # path must be a no-op (column already present), not raise.
    db_path = tmp_path / "mem.db"
    mem1 = MemoryManager(str(db_path))
    await mem1.init()
    mem2 = MemoryManager(str(db_path))
    await mem2.init()
    await mem2.record_cost(session_id="s1", tool="route_request", model="m", cost_usd=0.01, project_id="proj-a")


@pytest.mark.asyncio
async def test_record_cost_without_project_id_defaults_unscoped(tmp_path):
    mem = MemoryManager(str(tmp_path / "mem.db"))
    await mem.init()
    await mem.record_cost(session_id="s1", tool="route_request", model="m", cost_usd=0.01)
    logs = await mem.raw_cost_logs()
    assert logs[0]["project_id"] is None


@pytest.mark.asyncio
async def test_project_cost_report_groups_by_project(tmp_path):
    mem = MemoryManager(str(tmp_path / "mem.db"))
    await mem.init()
    await mem.record_cost(session_id="s1", tool="route_request", model="m", cost_usd=0.01, project_id="proj-a")
    await mem.record_cost(session_id="s1", tool="rewrite_prompt", model="m", cost_usd=0.02, project_id="proj-a")
    await mem.record_cost(session_id="s2", tool="route_request", model="m", cost_usd=0.005, project_id="proj-b")
    await mem.record_cost(session_id="s3", tool="route_request", model="m", cost_usd=0.001)

    rows = await mem.project_cost_report()
    by_id = {r["project_id"]: r for r in rows}
    assert by_id["proj-a"]["calls"] == 2
    assert round(by_id["proj-a"]["total_cost_usd"], 6) == 0.03
    assert by_id["proj-b"]["calls"] == 1
    assert by_id["unscoped"]["calls"] == 1


@pytest.mark.asyncio
async def test_raw_cost_logs_filters_by_project_id(tmp_path):
    mem = MemoryManager(str(tmp_path / "mem.db"))
    await mem.init()
    await mem.record_cost(session_id="s1", tool="t", model="m", cost_usd=0.01, project_id="proj-a")
    await mem.record_cost(session_id="s2", tool="t", model="m", cost_usd=0.02, project_id="proj-b")
    logs = await mem.raw_cost_logs(project_id="proj-a")
    assert len(logs) == 1
    assert logs[0]["project_id"] == "proj-a"


@pytest.mark.asyncio
async def test_project_cost_report_empty_db_returns_empty_list(tmp_path):
    mem = MemoryManager(str(tmp_path / "mem.db"))
    await mem.init()
    assert await mem.project_cost_report() == []
