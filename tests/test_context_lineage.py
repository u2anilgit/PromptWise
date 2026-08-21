from promptwise.core.audit_log import AuditLog
from promptwise.core.context_ranker import list_context_lineage, record_context_lineage
from promptwise.core.incidents import IncidentStore


def test_record_context_lineage_appends_audit_record(tmp_path):
    log = AuditLog(path=tmp_path / "audit.jsonl")
    result = record_context_lineage(
        log, retrieval_query="deploy runbook", shard_ids=["doc:s1", "doc:s2"],
        origin_path="docs/RUNBOOK.md")
    assert result["recorded"] is True
    assert result["origin"] == "docs/RUNBOOK.md"
    assert result["shard_ids"] == ["doc:s1", "doc:s2"]
    ok, _ = log.verify()
    assert ok


def test_record_context_lineage_mcp_server_origin_no_file(tmp_path):
    log = AuditLog(path=tmp_path / "audit.jsonl")
    result = record_context_lineage(
        log, retrieval_query="q", shard_ids=["audit:3"], mcp_server="promptwise-search")
    assert result["origin"] == "promptwise-search"
    rec = log.query(actor="context_lineage")[0]
    assert rec["files_touched"] == []


def test_list_context_lineage_filters_to_lineage_actor(tmp_path):
    log = AuditLog(path=tmp_path / "audit.jsonl")
    log.append("unrelated change", actor="dev")
    record_context_lineage(log, retrieval_query="q1", shard_ids=["doc:s1"], origin_path="a.md")
    record_context_lineage(log, retrieval_query="q2", shard_ids=["doc:s2"], origin_path="b.md")
    records = list_context_lineage(log)
    assert len(records) == 2
    assert all(r["actor"] == "context_lineage" for r in records)


def test_list_context_lineage_contains_filters_by_shard_id(tmp_path):
    log = AuditLog(path=tmp_path / "audit.jsonl")
    record_context_lineage(log, retrieval_query="q1", shard_ids=["doc:s1"], origin_path="a.md")
    record_context_lineage(log, retrieval_query="q2", shard_ids=["doc:s2"], origin_path="b.md")
    records = list_context_lineage(log, contains="doc:s2")
    assert len(records) == 1
    assert "shard:doc:s2" in records[0]["rules_applied"]


def test_incident_timeline_surfaces_lineage_via_correlation_key(tmp_path):
    """The spec's exact forensic scenario: 'what context poisoned this
    agent' (ASI06) -- incident_timeline's existing correlation_key
    substring match (see handlers/incidents.py:118-133) picks up a
    context_lineage record with zero incidents.py changes, because both
    read the same AuditLog. Reimplements that handler's exact merge logic
    inline against an injectable log (the real handler binds to the
    process-wide _get_audit_log() singleton, not an injectable one --
    Task 3 adds a handler-level test that monkeypatches that singleton
    for a true end-to-end check)."""
    log = AuditLog(path=tmp_path / "audit.jsonl")
    record_context_lineage(
        log, retrieval_query="q", shard_ids=["doc:poisoned-shard"],
        origin_path="untrusted/inbox.md")
    store = IncidentStore(db_path=tmp_path / "incidents.db")
    inc = store.create("agent acted on poisoned context")
    events = store.list_events(inc.id)
    timeline = [{"source": "incident_event", "ts": e.ts, **e.to_dict()} for e in events]
    audit_records = log.query(contains="untrusted/inbox.md")
    for rec in audit_records:
        timeline.append({"source": "audit", "ts": rec.get("timestamp", ""), **rec})
    timeline.sort(key=lambda e: e.get("ts", ""))
    assert any(e.get("source") == "audit" and e.get("actor") == "context_lineage" for e in timeline)
