"""Tests for ComplianceEngine."""

from pathlib import Path
from promptwise_v3.security.compliance import ComplianceEngine


def test_compliance_no_profile():
    c = ComplianceEngine()
    violations, redacted = c.check("Hello", "nonexistent")
    assert len(violations) == 0
    assert redacted == "Hello"


def test_compliance_load_and_check(tmp_path):
    c = ComplianceEngine()
    profile = tmp_path / "test_rules.yaml"
    profile.write_text("rules:\n  - name: no-password\n    pattern: password\n    action: redact\n", encoding="utf-8")
    c.load_profile("test_rules", path=profile)
    violations, redacted = c.check("My password is secret", "test_rules")
    assert len(violations) == 1, f"Expected 1 violation, got {violations}"
    assert "REDACTED" in redacted


def test_compliance_get_profiles():
    c = ComplianceEngine()
    assert c.get_loaded_profiles() == []
