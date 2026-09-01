"""WP3 — incident lifecycle: create/update/close with enforced status
transitions (open -> triaged -> contained -> resolved -> closed, no
skipping). First multi-state enforced transition graph in this codebase
(Approvals/LearningStore are both one-hop status flips, not a graph)."""
import pytest

from promptwise.core.incidents import Incident, IncidentEvent, IncidentStore


def test_create_incident_starts_open(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    inc = store.create("Suspicious prompt injection", severity="high")
    assert inc.status == "open"
    assert inc.title == "Suspicious prompt injection"
    assert inc.severity == "high"
    assert isinstance(inc.id, int)


def test_legal_transition_chain(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    inc = store.create("Test incident")
    for status in ("triaged", "contained", "resolved", "closed"):
        inc = store.update_status(inc.id, status, actor="alice")
        assert inc.status == status


def test_illegal_transition_rejected(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    inc = store.create("Test incident")
    with pytest.raises(ValueError, match="open"):
        store.update_status(inc.id, "closed", actor="alice")  # skip straight to closed


def test_illegal_backward_transition_rejected(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    inc = store.create("Test incident")
    store.update_status(inc.id, "triaged", actor="alice")
    with pytest.raises(ValueError):
        store.update_status(inc.id, "open", actor="alice")  # no going back


def test_update_status_unknown_incident_raises(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    with pytest.raises(ValueError, match="999"):
        store.update_status(999, "triaged", actor="alice")


def test_get_returns_none_for_unknown(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    assert store.get(999) is None


def test_list_all_filters_by_status(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    a = store.create("A")
    b = store.create("B")
    store.update_status(a.id, "triaged")
    assert len(store.list_all()) == 2
    assert len(store.list_all(status="open")) == 1
    assert len(store.list_all(status="triaged")) == 1


def test_add_event_and_list_events(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    inc = store.create("Test incident")
    store.add_event(inc.id, "detection", "anomaly finding attached", actor="detector")
    store.add_event(inc.id, "note", "reviewed by analyst", actor="alice")
    events = store.list_events(inc.id)
    assert len(events) == 2
    assert events[0].event_type == "detection"
    assert all(isinstance(e, IncidentEvent) for e in events)


def test_incident_metadata_round_trips(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    inc = store.create("Test", metadata={"source": "detect_anomalies", "finding_id": "abc"})
    reloaded = store.get(inc.id)
    assert reloaded.metadata == {"source": "detect_anomalies", "finding_id": "abc"}


def test_to_dict_shapes(tmp_path):
    store = IncidentStore(tmp_path / "incidents.db")
    inc = store.create("Test")
    d = inc.to_dict()
    assert set(d) >= {"id", "title", "severity", "status", "created_at", "updated_at", "description", "aivss_score", "metadata"}
    ev = store.add_event(inc.id, "note", "hello")
    ed = ev.to_dict()
    assert set(ed) >= {"id", "incident_id", "event_type", "detail", "actor", "ts"}


# ── MCP tool handlers ────────────────────────────────────────────────────────
import asyncio
import json as _json
import types
import typing

from promptwise.core.identity import Identity
from promptwise.core.tool_registry import ServerContext

import promptwise.server  # noqa: F401 -- forces ordered handler-module imports
                            # before we import handlers.incidents directly below,
                            # keeping _TOOL_DEFS registration order deterministic
                            # regardless of pytest collection order (see WP1 Task 6 /
                            # WP2 Tasks 3/5/7/9 for the bug this guards against).
from promptwise.handlers.incidents import _handle_create_incident, _handle_list_incidents

_ICTX = typing.cast(ServerContext, None)


def test_create_incident_tool(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    out = _json.loads(asyncio.run(_handle_create_incident(_ICTX, {
        "title": "Suspicious prompt injection", "severity": "high"})))
    assert out["status"] == "open"
    assert out["title"] == "Suspicious prompt injection"


def test_list_incidents_tool(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    asyncio.run(_handle_create_incident(_ICTX, {"title": "A"}))
    asyncio.run(_handle_create_incident(_ICTX, {"title": "B"}))
    out = _json.loads(asyncio.run(_handle_list_incidents(_ICTX, {})))
    assert len(out["incidents"]) == 2


from promptwise.handlers.incidents import _handle_update_incident, _handle_close_incident

# _handle_update_incident/_handle_close_incident read ctx.identity (actor
# auto-fill, Task 3) -- _ICTX (cast-from-None) can't stand in for those two;
# a minimal identity-carrying stub does.
_IDCTX = types.SimpleNamespace(identity=Identity(), remote_identity=None)


def test_update_incident_tool_transitions(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    created = _json.loads(asyncio.run(_handle_create_incident(_ICTX, {"title": "T"})))
    out = _json.loads(asyncio.run(_handle_update_incident(_IDCTX, {
        "incident_id": created["id"], "status": "triaged", "actor": "alice"})))
    assert out["status"] == "triaged"


def test_update_incident_tool_illegal_transition_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    created = _json.loads(asyncio.run(_handle_create_incident(_ICTX, {"title": "T"})))
    out = _json.loads(asyncio.run(_handle_update_incident(_IDCTX, {
        "incident_id": created["id"], "status": "closed", "actor": "alice"})))
    assert "error" in out


def test_close_incident_requires_resolved_status(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr("promptwise.core.learning_store.default_db_path", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    created = _json.loads(asyncio.run(_handle_create_incident(_ICTX, {"title": "T"})))
    out = _json.loads(asyncio.run(_handle_close_incident(_IDCTX, {
        "incident_id": created["id"], "mistake": "m", "correction": "c"})))
    assert "error" in out  # can't close an 'open' incident, must reach 'resolved' first


def test_close_incident_captures_learning(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr("promptwise.core.learning_store.default_db_path", lambda: tmp_path / "wp3.db")
    from promptwise.core.incidents import IncidentStore
    store = IncidentStore(tmp_path / "wp3.db")
    inc = store.create("T")
    for status in ("triaged", "contained", "resolved"):
        store.update_status(inc.id, status)
    out = _json.loads(asyncio.run(_handle_close_incident(_IDCTX, {
        "incident_id": inc.id, "mistake": "no rate limiting on the tool", "correction": "add throttle"})))
    assert out["status"] == "closed"
    assert out.get("learning_captured") is True


from promptwise.handlers.incidents import _handle_score_incident


def test_score_incident_tool_persists_score(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    created = _json.loads(asyncio.run(_handle_create_incident(_ICTX, {"title": "T"})))
    out = _json.loads(asyncio.run(_handle_score_incident(_ICTX, {
        "incident_id": created["id"],
        "factors": {"autonomy": 90.0, "tool_access": 80.0, "memory_persistence": 20.0, "multi_agent_reach": 10.0}})))
    assert out["aivss_score"] > 0
    from promptwise.core.incidents import IncidentStore
    reloaded = IncidentStore(tmp_path / "wp3.db").get(created["id"])
    assert reloaded.aivss_score == out["aivss_score"]


def test_score_incident_unknown_incident_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    out = _json.loads(asyncio.run(_handle_score_incident(_ICTX, {"incident_id": 999, "factors": {}})))
    assert "error" in out
