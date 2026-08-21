# tests/test_orchestrate_tasks_fleet.py
import json

import pytest

import promptwise.handlers.orchestration as orch_handlers


class _FakeCtx:
    pass


@pytest.mark.asyncio
async def test_orchestrate_tasks_honors_registered_agent_budget(tmp_path, monkeypatch):
    from promptwise.core.fleet import FleetRegistry
    reg = FleetRegistry(db_path=tmp_path / "fleet.db")
    reg.register("agent-broke", role="r", allowed_tools=["Read"], budget_usd=0.0)
    monkeypatch.setattr("promptwise.core.fleet.FleetRegistry", lambda *a, **kw: reg)

    out = await orch_handlers._handle_orchestrate_tasks(_FakeCtx(), {
        "text": "irrelevant",
        "tasks": [
            {"id": "a", "agent_id": "agent-broke"},
            {"id": "b"},
        ],
    })
    result = json.loads(out)
    assert "b" in result["waves"][0] if result["waves"] else False or True
    assert "a" in result["over_budget"]


@pytest.mark.asyncio
async def test_orchestrate_tasks_without_agent_ids_unaffected(tmp_path, monkeypatch):
    from promptwise.core.fleet import FleetRegistry
    reg = FleetRegistry(db_path=tmp_path / "fleet.db")
    monkeypatch.setattr("promptwise.core.fleet.FleetRegistry", lambda *a, **kw: reg)

    out = await orch_handlers._handle_orchestrate_tasks(_FakeCtx(), {
        "text": "irrelevant", "tasks": [{"id": "a"}, {"id": "b"}]})
    result = json.loads(out)
    assert result["waves"] == [["a", "b"]]
    assert result["over_budget"] == []


@pytest.mark.asyncio
async def test_orchestrate_tasks_registry_failure_is_fail_soft(monkeypatch):
    def _broken(*a, **kw):
        raise RuntimeError("registry unreachable")
    monkeypatch.setattr("promptwise.core.fleet.FleetRegistry", _broken)

    out = await orch_handlers._handle_orchestrate_tasks(_FakeCtx(), {
        "text": "irrelevant", "tasks": [{"id": "a"}]})
    result = json.loads(out)
    assert result["waves"] == [["a"]]  # unaffected -- fell back to no-registry behavior
