import json

import pytest

import promptwise.core.fleet as _fleet_module
import promptwise.handlers.fleet as fleet_handlers
from promptwise.core.audit_log import AuditLog

# Capture the real class once, before any test monkeypatches the module
# attribute -- a lambda that re-imports promptwise.core.fleet and reads
# .FleetRegistry from it would just call itself (the patched attribute),
# recursing forever. Binding the real class here avoids that trap.
_RealFleetRegistry = _fleet_module.FleetRegistry


class _FakeCtx:
    pass


def _patch_audit_log(monkeypatch, tmp_path):
    """detect_agent_drift/fleet_report handlers now fetch the real
    process-wide audit log via tool_registry._get_audit_log() -- point it
    at a tmp-path log so handler tests never touch the real repo-root
    promptwise_audit.jsonl file."""
    log = AuditLog(path=tmp_path / "handler_audit.jsonl")
    monkeypatch.setattr("promptwise.core.tool_registry._get_audit_log", lambda: log)
    return log


@pytest.mark.asyncio
async def test_register_agent_handler(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "promptwise.core.fleet.FleetRegistry",
        lambda *a, **kw: _RealFleetRegistry(db_path=tmp_path / "fleet.db"))
    out = await fleet_handlers._handle_register_agent(_FakeCtx(), {
        "agent_id": "agent-a", "role": "reviewer", "allowed_tools": ["Read", "Grep"],
        "budget_usd": 5.0, "owner": "team-x"})
    result = json.loads(out)
    assert result["agent_id"] == "agent-a"
    assert result["allowed_tools"] == ["Read", "Grep"]


@pytest.mark.asyncio
async def test_register_agent_prefills_from_detect_agents(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "promptwise.core.fleet.FleetRegistry",
        lambda *a, **kw: _RealFleetRegistry(db_path=tmp_path / "fleet.db"))
    (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    out = await fleet_handlers._handle_register_agent(_FakeCtx(), {
        "agent_id": "agent-a", "prefill_from_detect_agents": True, "repo_root": str(tmp_path)})
    result = json.loads(out)
    assert result["role"] == "claude"  # pre-filled from detect_agents() targets[0]


@pytest.mark.asyncio
async def test_detect_sprawl_handler_empty_registry_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "promptwise.core.fleet.FleetRegistry",
        lambda *a, **kw: _RealFleetRegistry(db_path=tmp_path / "fleet.db"))
    out = await fleet_handlers._handle_detect_sprawl(_FakeCtx(), {})
    result = json.loads(out)
    assert result == {"pairs": [], "role_duplicates": {}}


@pytest.mark.asyncio
async def test_detect_agent_drift_handler_unknown_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "promptwise.core.fleet.FleetRegistry",
        lambda *a, **kw: _RealFleetRegistry(db_path=tmp_path / "fleet.db"))
    _patch_audit_log(monkeypatch, tmp_path)
    out = await fleet_handlers._handle_detect_agent_drift(_FakeCtx(), {"agent_id": "ghost"})
    result = json.loads(out)
    assert result["type"] == "UnknownAgent"


@pytest.mark.asyncio
async def test_fleet_report_handler(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "promptwise.core.fleet.FleetRegistry",
        lambda *a, **kw: _RealFleetRegistry(db_path=tmp_path / "fleet.db"))
    _patch_audit_log(monkeypatch, tmp_path)
    out = await fleet_handlers._handle_fleet_report(_FakeCtx(), {})
    result = json.loads(out)
    assert result["agents"] == []
    assert result["generated_at"]
