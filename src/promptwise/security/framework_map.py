"""framework_map — multi-framework compliance report card (P1 Task 4).

Maps ``SecurityScanner`` violation ``check`` values (already produced by
``check()``, and re-exposed by ``run_security_suite`` / ``run_red_team_harness``
-- no new detection logic lives here) onto three external governance
frameworks simultaneously, promptfoo-style: OWASP LLM Top 10, NIST AI RMF,
and MITRE ATLAS.

Every category name below was fetched and verified this session (2026-07-23)
from the cited authoritative source -- never invented. A ``check`` value with
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

_TABLES = {
    "owasp_llm_top10": _CHECK_TO_OWASP_LLM,
    "nist_ai_rmf": _CHECK_TO_NIST_AI_RMF,
    "mitre_atlas": _CHECK_TO_MITRE_ATLAS,
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
