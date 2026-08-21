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


def test_correlate_twice_does_not_duplicate_match_rows(tmp_path):
    store = _seeded_store(tmp_path)
    correlate(store, atlas_technique_ids=["AML.T0051"], incident_id=42)
    correlate(store, atlas_technique_ids=["AML.T0051"], incident_id=42)
    conn = store._connect()
    try:
        rows = conn.execute("SELECT * FROM intel_matches WHERE incident_id = 42").fetchall()
    finally:
        conn.close()
    assert len(rows) == 1


def test_correlate_matches_bracketed_stix_pattern_syntax(tmp_path):
    store = ThreatIntelStore(db_path=tmp_path / "intel.db")
    store.upsert_objects({
        "indicators": [{"id": "indicator--2", "name": "real-stix-pattern",
                         "pattern": "[domain-name:value = 'evil.example.com']"}],
        "attack_patterns": [], "intrusion_sets": [], "relationships": [],
    }, source="test")
    matches = correlate(store, content="connection observed to evil.example.com", incident_id=7)
    assert len(matches) == 1
    assert matches[0]["matched_on"] == "indicator_pattern"
    assert matches[0]["stix_id"] == "indicator--2"


def test_correlate_bare_token_pattern_still_matches(tmp_path):
    # regression guard: the seed bundle's bare-token patterns (e.g.
    # "shai-hulud", not real STIX patterning syntax) must keep matching.
    store = ThreatIntelStore(db_path=tmp_path / "intel.db")
    store.upsert_objects({
        "indicators": [{"id": "indicator--3", "name": "bare-token",
                         "pattern": "shai-hulud"}],
        "attack_patterns": [], "intrusion_sets": [], "relationships": [],
    }, source="test")
    matches = correlate(store, content="detected SHAI-HULUD worm activity", incident_id=8)
    assert len(matches) == 1
    assert matches[0]["stix_id"] == "indicator--3"
