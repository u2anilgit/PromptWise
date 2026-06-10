"""Tests for LicenseChecker."""

from promptwise_v3.core.license_checker import LicenseChecker


def test_compatible_sbom():
    lc = LicenseChecker()
    sbom = {"components": [{"name": "requests", "version": "2.31.0"}]}
    result = lc.audit(sbom)
    assert result["compatible"] is True


def test_gpl_risk():
    lc = LicenseChecker()
    sbom = {"components": [{"name": "gpl-library", "version": "1.0.0"}]}
    result = lc.audit(sbom)
    assert result["compatible"] is False
    assert len(result["risks"]) > 0


def test_empty_sbom():
    lc = LicenseChecker()
    sbom = {"components": []}
    result = lc.audit(sbom)
    assert result["compatible"] is True
    assert result["audited_count"] == 0
