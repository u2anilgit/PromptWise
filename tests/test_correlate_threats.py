from promptwise.security.threat_intel import ThreatIntelStore, correlate


def _seeded_store(tmp_path):
    store = ThreatIntelStore(db_path=tmp_path / "intel.db")
    store.upsert_objects({
        "indicators": [{"id": "indicator--1", "name": "known-bad-domain",
                         "pattern": "evil.example.com"}],
        "attack_patterns": [{"id": "attack-pattern--1", "name": "Prompt Injection",
                              "external_references": [{"source_name": "mitre-atlas",
                                                         "external_id": "AML.T0051"}]}],
        "intrusion_sets": [], "relationships": [],
    }, source="test")
    return store


def test_correlate_matches_atlas_technique_id(tmp_path):
    store = _seeded_store(tmp_path)
    matches = correlate(store, atlas_technique_ids=["AML.T0051"], incident_id=42)
    assert len(matches) == 1
    assert matches[0]["matched_on"] == "atlas_technique_id"
    assert matches[0]["stix_id"] == "attack-pattern--1"


def test_correlate_matches_indicator_string(tmp_path):
    store = _seeded_store(tmp_path)
    matches = correlate(store, content="connection attempt to evil.example.com blocked", incident_id=42)
    assert len(matches) == 1
    assert matches[0]["matched_on"] == "indicator_pattern"
    assert matches[0]["stix_id"] == "indicator--1"


def test_correlate_no_match_returns_empty(tmp_path):
    store = _seeded_store(tmp_path)
    matches = correlate(store, content="nothing interesting here", atlas_technique_ids=["AML.T9999"])
    assert matches == []


def test_correlate_persists_match_row_when_incident_given(tmp_path):
    store = _seeded_store(tmp_path)
    correlate(store, atlas_technique_ids=["AML.T0051"], incident_id=42)
    conn = store._connect()
    try:
        rows = conn.execute("SELECT * FROM intel_matches WHERE incident_id = 42").fetchall()
    finally:
        conn.close()
    assert len(rows) == 1


def test_correlate_dry_probe_does_not_persist(tmp_path):
    store = _seeded_store(tmp_path)
    correlate(store, atlas_technique_ids=["AML.T0051"])  # no audit_record_id, no incident_id
    conn = store._connect()
    try:
        rows = conn.execute("SELECT * FROM intel_matches").fetchall()
    finally:
        conn.close()
    assert len(rows) == 0
