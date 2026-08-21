from promptwise.security.threat_intel import parse_bundle


def test_parses_supported_object_types():
    bundle = {
        "type": "bundle",
        "id": "bundle--test",
        "objects": [
            {"type": "indicator", "id": "indicator--1", "name": "known-bad-domain",
             "pattern": "[domain-name:value = 'evil.example.com']"},
            {"type": "attack-pattern", "id": "attack-pattern--1", "name": "Prompt Injection",
             "external_references": [{"source_name": "mitre-atlas", "external_id": "AML.T0051"}]},
            {"type": "intrusion-set", "id": "intrusion-set--1", "name": "GTG-1002"},
            {"type": "relationship", "id": "relationship--1", "relationship_type": "uses",
             "source_ref": "intrusion-set--1", "target_ref": "attack-pattern--1"},
        ],
    }
    result = parse_bundle(bundle)
    assert len(result["indicators"]) == 1
    assert result["indicators"][0]["id"] == "indicator--1"
    assert len(result["attack_patterns"]) == 1
    assert len(result["intrusion_sets"]) == 1
    assert len(result["relationships"]) == 1
    assert result["relationships"][0]["source_ref"] == "intrusion-set--1"


def test_unsupported_object_types_skipped_not_errored():
    bundle = {
        "type": "bundle", "id": "bundle--test",
        "objects": [
            {"type": "malware", "id": "malware--1", "name": "some-malware"},
            {"type": "campaign", "id": "campaign--1", "name": "some-campaign"},
            {"type": "indicator", "id": "indicator--1", "name": "ok", "pattern": "[x]"},
        ],
    }
    result = parse_bundle(bundle)
    assert len(result["indicators"]) == 1
    assert result["attack_patterns"] == []
    assert result["intrusion_sets"] == []
    assert result["relationships"] == []


def test_malformed_object_skipped():
    bundle = {
        "type": "bundle", "id": "bundle--test",
        "objects": [
            {"type": "indicator"},  # missing id/name/pattern -- malformed, skip
            {"type": "indicator", "id": "indicator--good", "name": "ok", "pattern": "[x]"},
        ],
    }
    result = parse_bundle(bundle)
    assert len(result["indicators"]) == 1
    assert result["indicators"][0]["id"] == "indicator--good"


def test_not_a_bundle_returns_empty_result():
    result = parse_bundle({"type": "not-a-bundle"})
    assert result == {"indicators": [], "attack_patterns": [], "intrusion_sets": [], "relationships": []}


import json

import pytest

from promptwise.security.threat_intel import ThreatIntelStore, import_bundle_file


def _store(tmp_path):
    return ThreatIntelStore(db_path=tmp_path / "intel.db")


def test_upsert_objects_dedups_by_stix_id(tmp_path):
    store = _store(tmp_path)
    parsed = {
        "indicators": [{"id": "indicator--1", "name": "bad-ip", "pattern": "[ipv4-addr:value = '1.2.3.4']"}],
        "attack_patterns": [], "intrusion_sets": [], "relationships": [],
    }
    inserted = store.upsert_objects(parsed, source="seed")
    assert inserted == 1
    # re-import the same object -- dedup, no duplicate row
    inserted_again = store.upsert_objects(parsed, source="seed")
    assert inserted_again == 1
    rows = store.list_objects("indicator")
    assert len(rows) == 1
    assert rows[0]["stix_id"] == "indicator--1"


def test_upsert_objects_extracts_atlas_technique_id(tmp_path):
    store = _store(tmp_path)
    parsed = {
        "indicators": [], "intrusion_sets": [], "relationships": [],
        "attack_patterns": [{
            "id": "attack-pattern--1", "name": "Prompt Injection",
            "external_references": [{"source_name": "mitre-atlas", "external_id": "AML.T0051"}],
        }],
    }
    store.upsert_objects(parsed, source="seed")
    row = store.get_by_stix_id("attack-pattern--1")
    assert row["atlas_technique_id"] == "AML.T0051"


def test_import_bundle_file_roundtrip(tmp_path):
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps({
        "type": "bundle", "id": "bundle--x",
        "objects": [{"id": "indicator--x", "type": "indicator", "name": "x", "pattern": "[x]"}],
    }), encoding="utf-8")
    store = _store(tmp_path)
    result = import_bundle_file(str(bundle_path), source="unit-test", store=store)
    assert result == {"imported": 1, "source": "unit-test"}
    assert store.get_by_stix_id("indicator--x") is not None


def test_import_bundle_file_missing_raises(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(FileNotFoundError):
        import_bundle_file(str(tmp_path / "missing.json"), source="x", store=store)
