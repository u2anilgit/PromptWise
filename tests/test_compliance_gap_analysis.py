import json

import pytest

from promptwise.security.framework_map import gap_analysis
import promptwise.handlers.compliance_export as compliance_export_handlers


def test_unknown_framework_returns_error_object():
    result = gap_analysis("not_a_real_framework", registered_tools=[])
    assert result["type"] == "UnknownFramework"
    assert "not_a_real_framework" not in result.get("available", [])


def test_gdpr_art33_implemented_when_both_tools_registered():
    result = gap_analysis("gdpr", registered_tools=["create_incident", "export_incident_bundle"])
    control = next(c for c in result["controls"] if c["control_id"] == "gdpr:art33")
    assert control["status"] == "implemented"
    assert set(control["evidenced_by"]) == {"create_incident", "export_incident_bundle"}


def test_gdpr_art32_partial_when_only_one_of_three_tools_registered():
    result = gap_analysis("gdpr", registered_tools=["run_security_suite"])
    control = next(c for c in result["controls"] if c["control_id"] == "gdpr:art32")
    assert control["status"] == "partial"
    assert control["evidenced_by"] == ["run_security_suite"]


def test_gdpr_art5_absent_when_no_tools_registered():
    result = gap_analysis("gdpr", registered_tools=[])
    control = next(c for c in result["controls"] if c["control_id"] == "gdpr:art5")
    assert control["status"] == "absent"
    assert control["evidenced_by"] == []


def test_gdpr_summary_counts_match_controls():
    result = gap_analysis("gdpr", registered_tools=["create_incident", "export_incident_bundle"])
    absent = sum(1 for c in result["controls"] if c["status"] == "absent")
    implemented = sum(1 for c in result["controls"] if c["status"] == "implemented")
    assert result["summary"]["absent"] == absent
    assert result["summary"]["implemented"] == implemented
    assert result["summary"]["implemented"] + result["summary"]["partial"] + result["summary"]["absent"] == len(result["controls"])


def test_hipaa_authentication_and_transmission_are_always_absent():
    """These two controls have an empty evidenced_by list by design (this
    codebase does no identity auth or network transport of its own) --
    they must report 'absent' regardless of what's registered, never a
    fabricated 'implemented'."""
    result = gap_analysis("hipaa", registered_tools=["grant_jit_permission", "record_audit", "export_compliance_bundle"])
    by_id = {c["control_id"]: c for c in result["controls"]}
    assert by_id["hipaa:164.312(d)"]["status"] == "absent"
    assert by_id["hipaa:164.312(e)"]["status"] == "absent"


def test_hipaa_audit_controls_implemented_when_all_four_tools_registered():
    result = gap_analysis("hipaa", registered_tools=["record_audit", "query_audit", "export_audit", "compact_audit"])
    control = next(c for c in result["controls"] if c["control_id"] == "hipaa:164.312(b)")
    assert control["status"] == "implemented"


def test_advisory_note_present_on_every_gap_analysis():
    result = gap_analysis("gdpr", registered_tools=[])
    assert "advisory" in result["advisory_note"].lower()
    assert "not a certification" in result["advisory_note"].lower() or "not a certification" in result["advisory_note"]


def test_owasp_nhi_top10_has_all_ten_controls():
    result = gap_analysis("owasp_nhi_top10", registered_tools=[])
    ids = {c["control_id"] for c in result["controls"]}
    assert ids == {f"nhi{i}" for i in range(1, 11)}


def test_nhi5_overprivileged_implemented_with_fleet_tools():
    result = gap_analysis("owasp_nhi_top10", registered_tools=["register_agent", "detect_sprawl"])
    control = next(c for c in result["controls"] if c["control_id"] == "nhi5")
    assert control["status"] == "implemented"


def test_nhi4_and_nhi6_and_nhi8_are_always_absent():
    result = gap_analysis("owasp_nhi_top10", registered_tools=[
        "register_agent", "detect_sprawl", "detect_agent_drift", "fleet_report",
        "revoke_jit_permission", "security_check", "scan_response", "audit_mcp_servers",
        "validate_dependencies", "get_sbom"])
    by_id = {c["control_id"]: c for c in result["controls"]}
    assert by_id["nhi4"]["status"] == "absent"
    assert by_id["nhi6"]["status"] == "absent"
    assert by_id["nhi8"]["status"] == "absent"


def test_csa_aicm_has_exactly_four_evidenced_domains():
    """Ground rule #8: CSA AICM has ~18 domains total, but this project's
    plan-research pass could only confirm 4 domain names from a live
    source fetch -- the other ~14 are intentionally omitted, not listed
    with an empty evidence list."""
    result = gap_analysis("csa_aicm", registered_tools=[])
    assert len(result["controls"]) == 4
    ids = {c["control_id"] for c in result["controls"]}
    assert ids == {"csa_aicm:iam", "csa_aicm:data_security", "csa_aicm:model_security", "csa_aicm:supply_chain"}


def test_csa_aicm_model_security_implemented_with_all_four_tools():
    result = gap_analysis("csa_aicm", registered_tools=[
        "prompt_injection", "benchmark_injection", "run_red_team_harness", "owasp_scan"])
    control = next(c for c in result["controls"] if c["control_id"] == "csa_aicm:model_security")
    assert control["status"] == "implemented"


class _FakeCtx:
    pass


@pytest.mark.asyncio
async def test_compliance_gap_analysis_handler_uses_real_registered_tools():
    out = await compliance_export_handlers._handle_compliance_gap_analysis(
        _FakeCtx(), {"framework": "gdpr"})
    result = json.loads(out)
    control = next(c for c in result["controls"] if c["control_id"] == "gdpr:art33")
    # create_incident and export_incident_bundle are real, currently-registered
    # tools -- this must reflect the live server, not a stub list.
    assert control["status"] == "implemented"


@pytest.mark.asyncio
async def test_compliance_gap_analysis_handler_unknown_framework():
    out = await compliance_export_handlers._handle_compliance_gap_analysis(
        _FakeCtx(), {"framework": "not_a_real_framework"})
    result = json.loads(out)
    assert result["type"] == "UnknownFramework"
