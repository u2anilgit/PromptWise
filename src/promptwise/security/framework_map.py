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


# ── WP6: required-control catalogs feeding gap_analysis() ─────────────────────
# Unlike _TABLES above (check-value -> category, which OMITS an unmapped
# check because it has no "required" list to be gapped against), each
# catalog here is a FULL required-control list for its framework -- a
# control with an empty evidenced_by is kept (never omitted) so
# gap_analysis() can honestly report it "absent". Every evidenced_by tool
# name below is drawn from the live `@tool(name=...)` registry (139 tools
# as of this plan's research pass, 2026-08-21) -- see this plan's "Research-
# verified real tool/check names" section and each task's own citation
# comments for the specific reasoning per control.
FRAMEWORK_SOURCES["gdpr"] = {
    "url": "https://gdpr-info.eu/",
    "fetched": "2026-08-21",
    "note": "GDPR (Regulation (EU) 2016/679), Arts. 5, 25, 32, 33 only -- the articles this codebase's audit/governance surface can genuinely evidence.",
}
FRAMEWORK_SOURCES["hipaa"] = {
    "url": "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-C/section-164.312",
    "fetched": "2026-08-21",
    "note": "HIPAA Security Rule, 45 CFR 164.312 Technical Safeguards (a)-(e).",
}
FRAMEWORK_SOURCES["owasp_nhi_top10"] = {
    "url": "https://owasp.org/www-project-non-human-identities-top-10/2025/top-10-2025/",
    "fetched": "2026-08-21",
    "note": "OWASP Non-Human Identities Top 10, 2025 edition, NHI1:2025-NHI10:2025.",
}
FRAMEWORK_SOURCES["csa_aicm"] = {
    "url": "https://cloudsecurityalliance.org/blog/2025/07/10/introducing-the-csa-ai-controls-matrix-a-comprehensive-framework-for-trustworthy-ai",
    "fetched": "2026-08-21",
    "note": (
        "CSA AI Controls Matrix (AICM) v1.1, 18 domains / 247 control "
        "objectives total. Only the 4 domains this codebase's checks can "
        "genuinely evidence are mapped -- the other ~14 domains are "
        "intentionally omitted (not listed with an empty evidence list), "
        "because this plan's live source fetch confirmed only these 4 "
        "domain names by title."
    ),
}

_REQUIRED_CONTROLS_GDPR = {
    "gdpr:art5": {
        "title": "Art. 5 Principles relating to processing of personal data",
        "evidenced_by": ["security_check", "scan_response"],
    },
    "gdpr:art25": {
        "title": "Art. 25 Data protection by design and by default",
        "evidenced_by": ["check_policy"],
    },
    "gdpr:art32": {
        "title": "Art. 32 Security of processing",
        "evidenced_by": ["run_security_suite", "export_compliance_bundle", "generate_ed25519_keypair"],
    },
    "gdpr:art33": {
        "title": "Art. 33 Notification of a personal data breach to the supervisory authority",
        "evidenced_by": ["create_incident", "export_incident_bundle"],
    },
}

_REQUIRED_CONTROLS_HIPAA = {
    "hipaa:164.312(a)": {
        "title": "§164.312(a) Access Control",
        "evidenced_by": ["grant_jit_permission", "list_jit_permissions", "revoke_jit_permission", "tune_permissions"],
    },
    "hipaa:164.312(b)": {
        "title": "§164.312(b) Audit Controls",
        "evidenced_by": ["record_audit", "query_audit", "export_audit", "compact_audit"],
    },
    "hipaa:164.312(c)": {
        "title": "§164.312(c) Integrity",
        "evidenced_by": ["export_compliance_bundle"],
    },
    "hipaa:164.312(d)": {
        "title": "§164.312(d) Person or Entity Authentication",
        "evidenced_by": [],  # no genuine evidence in this codebase -- always "absent"
    },
    "hipaa:164.312(e)": {
        "title": "§164.312(e) Transmission Security",
        "evidenced_by": [],  # offline-first tool, no network transport layer of its own
    },
}

_REQUIRED_CONTROLS_NHI = {
    "nhi1": {"title": "NHI1:2025 Improper Offboarding", "evidenced_by": ["revoke_jit_permission"]},
    "nhi2": {"title": "NHI2:2025 Secret Leakage", "evidenced_by": ["security_check", "scan_response"]},
    "nhi3": {"title": "NHI3:2025 Vulnerable Third-Party NHI", "evidenced_by": ["audit_mcp_servers", "validate_dependencies", "get_sbom"]},
    "nhi4": {"title": "NHI4:2025 Insecure Authentication", "evidenced_by": []},
    "nhi5": {"title": "NHI5:2025 Overprivileged NHI", "evidenced_by": ["register_agent", "detect_sprawl"]},
    "nhi6": {"title": "NHI6:2025 Insecure Cloud Deployment Configurations", "evidenced_by": []},
    "nhi7": {"title": "NHI7:2025 Long-Lived Secrets", "evidenced_by": ["register_agent", "fleet_report"]},
    "nhi8": {"title": "NHI8:2025 Environment Isolation", "evidenced_by": []},
    "nhi9": {"title": "NHI9:2025 NHI Reuse", "evidenced_by": ["detect_sprawl"]},
    "nhi10": {"title": "NHI10:2025 Human Use of NHI", "evidenced_by": ["detect_agent_drift"]},
}

_REQUIRED_CONTROLS_CSA_AICM = {
    "csa_aicm:iam": {
        "title": "Identity & Access Management",
        "evidenced_by": ["grant_jit_permission", "revoke_jit_permission", "list_jit_permissions", "register_agent"],
    },
    "csa_aicm:data_security": {
        "title": "Data Security & Privacy Lifecycle Management",
        "evidenced_by": ["security_check", "scan_response", "export_compliance_bundle"],
    },
    "csa_aicm:model_security": {
        "title": "Model Security",
        "evidenced_by": ["prompt_injection", "benchmark_injection", "run_red_team_harness", "owasp_scan"],
    },
    "csa_aicm:supply_chain": {
        "title": "Supply Chain Management, Transparency, & Accountability",
        "evidenced_by": ["validate_dependencies", "get_sbom", "audit_mcp_servers", "import_threat_feed"],
    },
}

_REQUIRED_CONTROLS: dict[str, dict] = {
    "gdpr": _REQUIRED_CONTROLS_GDPR,
    "hipaa": _REQUIRED_CONTROLS_HIPAA,
    "owasp_nhi_top10": _REQUIRED_CONTROLS_NHI,
    "csa_aicm": _REQUIRED_CONTROLS_CSA_AICM,
}


def gap_analysis(framework: str, registered_tools: list[str]) -> dict:
    """Per-framework required-control checklist vs controls evidenced by
    `registered_tools` (the caller's live tool-name list -- see
    handlers/compliance_export.py for the production caller). A control
    is "implemented" when every one of its evidenced_by tools is
    registered, "partial" when some but not all are, and "absent" when
    none are (including controls with a genuinely empty evidenced_by
    list -- an honest gap, not a fabrication). Advisory starting point,
    never a certification."""
    catalog = _REQUIRED_CONTROLS.get(framework)
    if catalog is None:
        return {"error": f"unknown framework '{framework}'", "type": "UnknownFramework",
                "available": sorted(_REQUIRED_CONTROLS)}
    registered = set(registered_tools)
    controls = []
    counts = {"implemented": 0, "partial": 0, "absent": 0}
    for control_id, spec in catalog.items():
        required = spec["evidenced_by"]
        evidence = [t for t in required if t in registered]
        if not required or not evidence:
            status = "absent"
        elif len(evidence) == len(required):
            status = "implemented"
        else:
            status = "partial"
        counts[status] += 1
        controls.append({
            "control_id": control_id, "title": spec["title"], "status": status,
            "evidenced_by": evidence,
        })
    return {
        "framework": framework, "source": FRAMEWORK_SOURCES.get(framework, {}),
        "controls": controls, "summary": counts,
        "advisory_note": "Advisory starting point, not a certification -- see GAP_ANALYSIS item 10.",
    }
