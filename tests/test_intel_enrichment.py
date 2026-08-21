import json

import pytest

from promptwise.core.audit_log import AuditLog
from promptwise.security.threat_intel import (
    ThreatIntelStore, correlate, enrich_audit, export_indicators,
)


def _seeded_store(tmp_path):
    store = ThreatIntelStore(db_path=tmp_path / "intel.db")
    store.upsert_objects({
        "indicators": [{"id": "indicator--1", "name": "known-bad-domain", "pattern": "evil.example.com"}],
        "attack_patterns": [], "intrusion_sets": [], "relationships": [],
    }, source="test")
    return store


def test_enrich_audit_appends_without_mutating_prior_records(tmp_path):
    store = _seeded_store(tmp_path)
    log = AuditLog(path=tmp_path / "audit.jsonl")
    rec = log.append("original task", actor="test")
    correlate(store, content="hit evil.example.com", audit_record_id=str(rec.index))

    result = enrich_audit(store, log, str(rec.index))
    assert result["enriched"] is True
    assert len(result["matches"]) == 1

    ok, msg = log.verify()
    assert ok, msg
    # original record untouched -- enrichment is a NEW record, not a mutation
    assert log.records[0].task == "original task"
    assert log.records[-1].task != "original task"


def test_enrich_audit_no_matches_returns_not_enriched(tmp_path):
    store = _seeded_store(tmp_path)
    log = AuditLog(path=tmp_path / "audit.jsonl")
    rec = log.append("unrelated task", actor="test")
    result = enrich_audit(store, log, str(rec.index))
    assert result == {"audit_record_id": str(rec.index), "matches": [], "enriched": False}


def test_export_indicators_json(tmp_path):
    store = _seeded_store(tmp_path)
    out = export_indicators(store, fmt="json")
    parsed = json.loads(out)
    assert len(parsed["indicators"]) == 1
    assert parsed["indicators"][0]["stix_id"] == "indicator--1"


def test_export_indicators_unsupported_format_raises(tmp_path):
    store = _seeded_store(tmp_path)
    with pytest.raises(ValueError):
        export_indicators(store, fmt="csv")
