# tests/test_orchestrate_tasks_fleet.py
import json

import pytest

import promptwise.handlers.orchestration as orch_handlers


class _FakeCtx:
    pass


@pytest.mark.asyncio
async def test_orchestrate_tasks_forwards_over_budget_status_to_plan(monkeypatch):
    """Regardless of how agent_budget_status is derived, the handler must
    correctly thread an already-exhausted agent through to plan_waves and
    surface it in over_budget. (budget_usd <= 0 from the registry itself
    means "not configured" per the ruling below and is never forwarded as
    exhausted -- see the next test -- so this exercises the wiring
    directly against _fleet_planning_hints' output.)"""
    monkeypatch.setattr(
        "promptwise.handlers.orchestration._fleet_planning_hints",
        lambda tasks_arg: ({}, {"agent-broke": {"remaining_usd": 0.0}}))

    out = await orch_handlers._handle_orchestrate_tasks(_FakeCtx(), {
        "text": "irrelevant",
        "tasks": [
            {"id": "a", "agent_id": "agent-broke"},
            {"id": "b"},
        ],
    })
    result = json.loads(out)
    assert result["waves"] == [["b"]]
    assert "a" in result["over_budget"]


@pytest.mark.asyncio
async def test_orchestrate_tasks_default_zero_budget_not_over_budget(tmp_path, monkeypatch):
    """register_agent's default budget_usd=0.0 means 'not configured', not
    'zero remaining budget' -- an agent registered with no explicit budget
    must never be excluded from waves as over_budget."""
    from promptwise.core.fleet import FleetRegistry
    reg = FleetRegistry(db_path=tmp_path / "fleet.db")
    reg.register("agent-unconfigured", role="r", allowed_tools=["Read"])  # budget_usd defaults to 0.0
    monkeypatch.setattr("promptwise.core.fleet.FleetRegistry", lambda *a, **kw: reg)

    out = await orch_handlers._handle_orchestrate_tasks(_FakeCtx(), {
        "text": "irrelevant",
        "tasks": [{"id": "a", "agent_id": "agent-unconfigured"}],
    })
    result = json.loads(out)
    assert result["over_budget"] == []
    assert result["waves"] == [["a"]]


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
