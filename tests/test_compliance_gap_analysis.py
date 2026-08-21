from promptwise.security.framework_map import gap_analysis


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
