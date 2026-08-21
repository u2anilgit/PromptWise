import json

import pytest

import promptwise.server  # noqa: F401 -- collection-order guard, see WP1 Task 6 / WP2 Tasks 3/5/7/9 / WP4 Task 6/8 for the bug this guards against

import promptwise.handlers.incidents as incidents_handlers


class _FakeCtx:
    pass


@pytest.mark.asyncio
async def test_create_incident_auto_correlates(tmp_path, monkeypatch):
    from promptwise.security.threat_intel import ThreatIntelStore

    # seed the default-resolved store the handler will use
    monkeypatch.setattr(
        "promptwise.security.threat_intel.ThreatIntelStore",
        lambda *a, **kw: ThreatIntelStore(db_path=tmp_path / "intel.db"))
    store = ThreatIntelStore(db_path=tmp_path / "intel.db")
    store.upsert_objects({
        "indicators": [{"id": "indicator--1", "name": "bad", "pattern": "evil.example.com"}],
        "attack_patterns": [], "intrusion_sets": [], "relationships": [],
    }, source="test")

    from promptwise.core.incidents import IncidentStore
    monkeypatch.setattr(
        "promptwise.core.incidents.IncidentStore",
        lambda *a, **kw: IncidentStore(db_path=tmp_path / "incidents.db"))

    out = await incidents_handlers._handle_create_incident(_FakeCtx(), {
        "title": "suspicious outbound connection",
        "description": "process reached out to evil.example.com",
    })
    result = json.loads(out)
    assert len(result["intel_matches"]) == 1
    match = result["intel_matches"][0]
    assert match["matched_on"] == "indicator_pattern"
    assert match["stix_id"] == "indicator--1"
    assert match["name"] == "bad"


@pytest.mark.asyncio
async def test_create_incident_correlation_failure_does_not_block_creation(tmp_path, monkeypatch):
    from promptwise.core.incidents import IncidentStore
    monkeypatch.setattr(
        "promptwise.core.incidents.IncidentStore",
        lambda *a, **kw: IncidentStore(db_path=tmp_path / "incidents.db"))
    # ThreatIntelStore() is constructed as an argument to correlate(...)
    # before correlate() itself is reached, so it must also be redirected
    # away from the real user db even though correlate() is what's patched
    # to raise below.
    monkeypatch.setattr(
        "promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")

    def _broken_correlate(*a, **kw):
        raise RuntimeError("intel store unreachable")

    monkeypatch.setattr("promptwise.security.threat_intel.correlate", _broken_correlate)

    out = await incidents_handlers._handle_create_incident(_FakeCtx(), {"title": "test incident"})
    result = json.loads(out)
    assert result["title"] == "test incident"
    assert result["intel_matches"] == []
