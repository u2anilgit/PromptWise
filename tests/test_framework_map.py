"""Task 4 (P1) — multi-framework compliance report card.

Maps SecurityScanner violation ``check`` values (already produced by
``check()``/``run_security_suite``/``run_red_team_harness`` -- no new
detection logic here) onto three external frameworks simultaneously:
OWASP LLM Top 10 (2025), NIST AI RMF, and MITRE ATLAS. Category names are
cited in ``framework_map.py`` from sources fetched this session; this test
file only asserts the mapping, not the citations.
"""
from promptwise.security.framework_map import build_report_card, FRAMEWORK_SOURCES


def test_injection_violation_maps_to_all_three_frameworks():
    violations = [{"check": "injection", "detail": "Injection: instruction_override"}]
    card = build_report_card(violations)
    assert card["owasp_llm_top10"] == ["LLM01:2025 Prompt Injection"]
    assert card["nist_ai_rmf"] == ["MEASURE 2: AI systems are evaluated for trustworthy characteristics"]
    assert card["mitre_atlas"] == ["AML.TA0004 Initial Access"]


def test_pii_violation_maps_to_sensitive_information_disclosure():
    violations = [{"check": "pii", "detail": "Found PII: email"}]
    card = build_report_card(violations)
    assert "LLM02:2025 Sensitive Information Disclosure" in card["owasp_llm_top10"]


def test_supply_chain_violation_maps_to_supply_chain_category():
    violations = [{"check": "supply_chain", "detail": "pipe-to-shell install"}]
    card = build_report_card(violations)
    assert "LLM03:2025 Supply Chain Vulnerabilities" in card["owasp_llm_top10"]
    assert "GOVERN 6: Policies and procedures for third-party software, data, and supply chain issues" in card["nist_ai_rmf"]


def test_unmapped_check_is_dropped_not_fabricated():
    """'secrets' has no dedicated ATLAS tactic in our cited source -- it
    must be omitted from that framework's list rather than guessing one."""
    violations = [{"check": "secrets", "detail": "hardcoded key"}]
    card = build_report_card(violations)
    assert card["mitre_atlas"] == []
    assert card["owasp_llm_top10"] == ["LLM02:2025 Sensitive Information Disclosure"]


def test_no_violations_yields_empty_lists_for_every_framework():
    card = build_report_card([])
    assert card == {
        "owasp_llm_top10": [], "nist_ai_rmf": [], "mitre_atlas": [],
        "soc2": [], "iso_42001": [], "eu_ai_act": [],
    }


def test_duplicate_checks_do_not_duplicate_categories():
    violations = [
        {"check": "injection", "detail": "a"},
        {"check": "injection", "detail": "b"},
    ]
    card = build_report_card(violations)
    assert card["owasp_llm_top10"] == ["LLM01:2025 Prompt Injection"]


def test_framework_sources_are_cited():
    assert set(FRAMEWORK_SOURCES) == {
        "owasp_llm_top10", "nist_ai_rmf", "mitre_atlas",
        "soc2", "iso_42001", "eu_ai_act",
    }
    for meta in FRAMEWORK_SOURCES.values():
        assert meta["url"].startswith("https://")
        assert meta["fetched"]


# ---------- SOC2 ----------
def test_injection_violation_maps_to_soc2_boundary_protection():
    violations = [{"check": "injection", "detail": "Injection: instruction_override"}]
    card = build_report_card(violations)
    assert card["soc2"] == ["CC6.6 Boundary Protection"]


def test_supply_chain_violation_maps_to_soc2_vendor_risk():
    violations = [{"check": "supply_chain", "detail": "pipe-to-shell install"}]
    card = build_report_card(violations)
    assert "CC9.2 Vendor and Business Partner Risk Management" in card["soc2"]


def test_secrets_violation_maps_to_soc2_confidentiality():
    violations = [{"check": "secrets", "detail": "hardcoded key"}]
    card = build_report_card(violations)
    assert card["soc2"] == ["C1.1 Confidentiality"]


# ---------- ISO 42001 ----------
def test_injection_violation_maps_to_iso42001_operation_monitoring():
    violations = [{"check": "injection", "detail": "Injection: instruction_override"}]
    card = build_report_card(violations)
    assert card["iso_42001"] == ["A.6.2.6 AI system operation and monitoring"]


def test_supply_chain_violation_maps_to_iso42001_suppliers():
    violations = [{"check": "supply_chain", "detail": "pipe-to-shell install"}]
    card = build_report_card(violations)
    assert "A.10.3 Suppliers" in card["iso_42001"]


def test_secrets_and_destructive_are_dropped_not_fabricated_for_iso42001():
    """No evidenced ISO 42001 category exists for 'secrets' or 'destructive'
    -- both must be omitted rather than guessing one (same discipline as
    the existing MITRE ATLAS table's omission of 'secrets'/'pii')."""
    violations = [
        {"check": "secrets", "detail": "hardcoded key"},
        {"check": "destructive", "detail": "destructive shell pattern match"},
    ]
    card = build_report_card(violations)
    assert card["iso_42001"] == []


# ---------- EU AI Act ----------
def test_injection_violation_maps_to_eu_ai_act_article_15():
    violations = [{"check": "injection", "detail": "Injection: instruction_override"}]
    card = build_report_card(violations)
    assert card["eu_ai_act"] == ["Art. 15 Cybersecurity (resilience to unauthorized manipulation)"]


def test_pii_violation_maps_to_eu_ai_act_article_10():
    violations = [{"check": "pii", "detail": "Found PII: email"}]
    card = build_report_card(violations)
    assert "Art. 10 Data Governance" in card["eu_ai_act"]


def test_permissions_violation_maps_to_eu_ai_act_article_14():
    violations = [{"check": "permissions", "detail": "overly broad grant"}]
    card = build_report_card(violations)
    assert "Art. 14 Human Oversight" in card["eu_ai_act"]


def test_supply_chain_violation_maps_to_eu_ai_act_article_25():
    violations = [{"check": "supply_chain", "detail": "pipe-to-shell install"}]
    card = build_report_card(violations)
    assert "Art. 25 Responsibilities along the AI Value Chain" in card["eu_ai_act"]


# ---------- cross-cutting ----------
def test_duplicate_checks_do_not_duplicate_categories_new_frameworks():
    violations = [
        {"check": "injection", "detail": "a"},
        {"check": "injection", "detail": "b"},
    ]
    card = build_report_card(violations)
    assert card["soc2"] == ["CC6.6 Boundary Protection"]
    assert card["iso_42001"] == ["A.6.2.6 AI system operation and monitoring"]
    assert card["eu_ai_act"] == ["Art. 15 Cybersecurity (resilience to unauthorized manipulation)"]
