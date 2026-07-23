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
    assert card == {"owasp_llm_top10": [], "nist_ai_rmf": [], "mitre_atlas": []}


def test_duplicate_checks_do_not_duplicate_categories():
    violations = [
        {"check": "injection", "detail": "a"},
        {"check": "injection", "detail": "b"},
    ]
    card = build_report_card(violations)
    assert card["owasp_llm_top10"] == ["LLM01:2025 Prompt Injection"]


def test_framework_sources_are_cited():
    assert set(FRAMEWORK_SOURCES) == {"owasp_llm_top10", "nist_ai_rmf", "mitre_atlas"}
    for meta in FRAMEWORK_SOURCES.values():
        assert meta["url"].startswith("https://")
        assert meta["fetched"]
