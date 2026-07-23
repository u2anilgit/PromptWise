"""framework_map — multi-framework compliance report card (P1 Task 4).

Maps ``SecurityScanner`` violation ``check`` values (already produced by
``check()``, and re-exposed by ``run_security_suite`` / ``run_red_team_harness``
-- no new detection logic lives here) onto six external governance
frameworks simultaneously, promptfoo-style: OWASP LLM Top 10, NIST AI RMF,
MITRE ATLAS, SOC 2, ISO/IEC 42001, and the EU AI Act.

Every category name below was fetched and verified this session (2026-07-23
for OWASP LLM Top 10 / NIST AI RMF / MITRE ATLAS; 2026-07-24 for SOC 2 /
ISO 42001 / EU AI Act) from the cited authoritative source -- never invented.
A ``check`` value with
no evidenced category in a given framework is simply omitted from that
framework's list; it is not guessed or forced to a "closest" category. This
follows the same anti-fabrication discipline as ``mcp_auditor.py``'s OWASP
MCP Top 10 mapping (P0 Task 3).
"""
from __future__ import annotations

FRAMEWORK_SOURCES = {
    "owasp_llm_top10": {
        "url": "https://owasp.org/www-project-top-10-for-large-language-model-applications/",
        "fetched": "2026-07-23",
        "note": "OWASP Top 10 for LLM Applications 2025 (v2.0), LLM01:2025-LLM10:2025.",
    },
    "nist_ai_rmf": {
        "url": "https://airc.nist.gov/airmf-resources/airmf/5-sec-core/",
        "fetched": "2026-07-23",
        "note": "NIST AI RMF 1.0 Core: GOVERN/MAP/MEASURE/MANAGE functions and categories.",
    },
    "mitre_atlas": {
        "url": "https://github.com/mitre-atlas/atlas-data",
        "fetched": "2026-07-23",
        "note": "MITRE ATLAS tactics (AML.TAxxxx), ATLAS.yaml, v5.4.0.",
    },
    "soc2": {
        "url": "https://truvocyber.com/blog/soc-2-trust-services-criteria-guide",
        "fetched": "2026-07-24",
        "note": "AICPA SOC 2 Trust Services Criteria: Common Criteria (CC1-CC9), Confidentiality (C1.x), Privacy (P1-P8).",
    },
    "iso_42001": {
        "url": "https://mindsetcyber.com.au/iso-42001-controls-list/",
        "fetched": "2026-07-24",
        "note": "ISO/IEC 42001:2023 Annex A controls (AI management system).",
    },
    "eu_ai_act": {
        "url": "https://www.euaiact.com/",
        "fetched": "2026-07-24",
        "note": "EU AI Act (Regulation (EU) 2024/1689), high-risk AI system obligations (Articles 10, 14, 15, 25).",
    },
}

# check-value -> category, one framework per table. Only checks with a real,
# evidenced correspondence appear; everything else maps to nothing for that
# framework (see test_unmapped_check_is_dropped_not_fabricated).
_CHECK_TO_OWASP_LLM = {
    "injection": "LLM01:2025 Prompt Injection",
    "pii": "LLM02:2025 Sensitive Information Disclosure",
    "secrets": "LLM02:2025 Sensitive Information Disclosure",
    "supply_chain": "LLM03:2025 Supply Chain Vulnerabilities",
    "destructive": "LLM06:2025 Excessive Agency",
    "permissions": "LLM06:2025 Excessive Agency",
}

_CHECK_TO_NIST_AI_RMF = {
    "injection": "MEASURE 2: AI systems are evaluated for trustworthy characteristics",
    "pii": "MAP 5: Impacts to individuals, groups, communities, organizations, and society",
    "supply_chain": "GOVERN 6: Policies and procedures for third-party software, data, and supply chain issues",
    "destructive": "MANAGE 1: AI risks are prioritized, responded to, and managed",
    "permissions": "MANAGE 1: AI risks are prioritized, responded to, and managed",
}

_CHECK_TO_MITRE_ATLAS = {
    "injection": "AML.TA0004 Initial Access",
    "supply_chain": "AML.TA0003 Resource Development",
    "destructive": "AML.TA0012 Privilege Escalation",
    "permissions": "AML.TA0012 Privilege Escalation",
}

_CHECK_TO_SOC2 = {
    "injection": "CC6.6 Boundary Protection",
    "secrets": "C1.1 Confidentiality",
    "pii": "Privacy category (P1-P8)",
    "supply_chain": "CC9.2 Vendor and Business Partner Risk Management",
    "destructive": "CC6.8 Malware Prevention",
    "permissions": "CC6.3 Role-Based Access and Least Privilege",
}

_CHECK_TO_ISO42001 = {
    "injection": "A.6.2.6 AI system operation and monitoring",
    "supply_chain": "A.10.3 Suppliers",
    "permissions": "A.9.2 Processes for responsible use of AI systems",
    # 'secrets', 'destructive', and 'pii' have no evidenced ISO 42001
    # category -- omitted per this module's anti-fabrication discipline
    # (ISO 42001 defers general information-security and personal-data
    # protection specifics to ISO 27001/other standards; A.7.4's "data
    # quality" scope covers accuracy/completeness/representativeness,
    # not privacy/disclosure protection, so it is not a genuine fit for
    # the 'pii' check).
}

_CHECK_TO_EU_AI_ACT = {
    "injection": "Art. 15 Cybersecurity (resilience to unauthorized manipulation)",
    "secrets": "Art. 15 Cybersecurity (confidentiality attacks)",
    "pii": "Art. 10 Data Governance",
    "supply_chain": "Art. 25 Responsibilities along the AI Value Chain",
    "destructive": "Art. 15 Robustness (resilience to errors/faults)",
    "permissions": "Art. 14 Human Oversight",
}

_TABLES = {
    "owasp_llm_top10": _CHECK_TO_OWASP_LLM,
    "nist_ai_rmf": _CHECK_TO_NIST_AI_RMF,
    "mitre_atlas": _CHECK_TO_MITRE_ATLAS,
    "soc2": _CHECK_TO_SOC2,
    "iso_42001": _CHECK_TO_ISO42001,
    "eu_ai_act": _CHECK_TO_EU_AI_ACT,
}


def build_report_card(violations: list[dict]) -> dict[str, list[str]]:
    """Build a per-framework list of evidenced categories from ``violations``.

    ``violations`` is the same list shape ``SecurityScanner.check()`` /
    ``run_security_suite`` / ``run_red_team_harness`` already produce
    (``{"check": <name>, "detail": ...}``). Categories are deduplicated and
    order-stable; a ``check`` value absent from a framework's table
    contributes nothing to that framework (never a fabricated category).
    """
    checks = [v.get("check") for v in violations if isinstance(v, dict)]
    card: dict[str, list[str]] = {}
    for framework, table in _TABLES.items():
        seen: list[str] = []
        for check in checks:
            category = table.get(check)
            if category and category not in seen:
                seen.append(category)
        card[framework] = seen
    return card
