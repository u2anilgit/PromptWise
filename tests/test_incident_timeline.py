"""WP3 -- incident_timeline: merge IncidentStore events with matching
AuditLog records into one chronological view. The payoff of the
tamper-evident hash-chained audit design (WP1): a forensic timeline that
can't have been quietly edited after the fact.
"""
import asyncio
import json
import typing

from promptwise.core.audit_log import AuditLog
from promptwise.core.incidents import IncidentStore
from promptwise.core.tool_registry import ServerContext

import promptwise.server  # noqa: F401 -- collection-order guard, see Task 2
from promptwise.handlers.incidents import _handle_incident_timeline

_TCTX = typing.cast(ServerContext, None)


def test_incident_timeline_merges_events_and_audit_records(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr(
        "promptwise.handlers.incidents._get_audit_log",
        lambda: AuditLog(tmp_path / "audit.jsonl"))

    store = IncidentStore(tmp_path / "wp3.db")
    inc = store.create("Test incident")
    store.add_event(inc.id, "detection", "anomaly finding attached", actor="detector")

    audit = AuditLog(tmp_path / "audit.jsonl")
    audit.append("anomaly_detected", actor="alice", rules_applied=["novel_tool_sequence"])
    audit.append("unrelated_task", actor="bob", rules_applied=["other"])

    out = json.loads(asyncio.run(_handle_incident_timeline(_TCTX, {
        "incident_id": inc.id, "correlation_key": "novel_tool_sequence"})))

    kinds = {(e["source"], e.get("task") or e.get("event_type")) for e in out["timeline"]}
    assert ("incident_event", "detection") in kinds
    assert ("audit", "anomaly_detected") in kinds
    assert not any(e.get("task") == "unrelated_task" for e in out["timeline"])


def test_incident_timeline_unknown_incident_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    out = json.loads(asyncio.run(_handle_incident_timeline(_TCTX, {
        "incident_id": 999, "correlation_key": "x"})))
    assert "error" in out
