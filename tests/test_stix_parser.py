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
