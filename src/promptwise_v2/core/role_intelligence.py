import re
from promptwise_v2.types_v2 import RoleProfile

_ROLE_KEYWORDS: dict[str, list[str]] = {
    "developer": [
        "function", "class", "debug", "test", "refactor", "code", "bug",
        "implement", "api", "unit test", "pytest", "script", "module", "python",
        "javascript", "typescript", "go", "rust", "java"
    ],
    "analyst": [
        "analyze", "metric", "trend", "report", "data", "sql", "dashboard",
        "kpi", "insight", "chart", "statistics", "performance"
    ],
    "researcher": [
        "research", "synthesize", "novel", "investigate", "literature",
        "compare", "hypothesis", "survey", "explore", "study"
    ],
    "manager": [
        "stakeholder", "status", "roadmap", "prioritize", "plan", "team",
        "sprint", "project", "deadline", "milestone", "update", "summary"
    ],
    "writer": [
        "draft", "blog", "article", "essay", "copy", "content", "write",
        "narrative", "editorial", "proofread", "edit"
    ],
    "designer": [
        "design", "ui", "ux", "component", "layout", "accessibility",
        "figma", "wireframe", "prototype", "visual", "interface"
    ],
    "IT": [
        "security", "infrastructure", "deployment", "observability", "pipeline",
        "cve", "sbom", "terraform", "ansible", "cloud", "docker", "kubernetes",
        "aws", "gcp", "azure"
    ],
    "PM": [
        "prd", "brd", "user stories", "roadmap", "feature", "prioritization",
        "okr", "market", "product", "stakeholder", "competitor"
    ],
    "EM": [
        "capacity", "sprint", "velocity", "debt", "performance", "review",
        "hiring", "team", "engineer"
    ],
    "SM": [
        "retro", "ceremony", "backlog", "grooming", "impediment", "velocity",
        "scrum", "agile", "sprint planning"
    ],
    "NTM": [
        "summary", "executive", "status", "risk", "budget", "communication",
        "plain language", "narrative"
    ],
    "Banking": [
        "regulatory", "compliance", "finra", "basel", "pci", "aml", "reconciliation",
        "credit", "risk", "financial", "transaction", "audit", "laundering"
    ],
    "Legal": [
        "contract", "gdpr", "ccpa", "license", "ip", "intellectual property",
        "clause", "privacy", "regulation", "law", "attorney"
    ],
    "Healthcare": [
        "hipaa", "fhir", "hl7", "clinical", "fda", "patient", "medical",
        "phi", "doctor", "health", "hospital"
    ],
    "HR": [
        "job description", "interview", "hiring", "onboarding", "dei",
        "compensation", "people", "performance review", "recruitment", "talent"
    ],
    "Data": [
        "sql", "pipeline", "database", "query", "analytics", "bi", "spark",
        "dbt", "warehouse", "etl", "ab test", "model card"
    ],
    "CSuite": [
        "board", "investor", "roi", "m&a", "strategy", "due diligence",
        "executive briefing", "c-suite", "revenue", "financial target"
    ],
    "Security": [
        "stride", "threat", "vulnerability", "pentest", "soc2", "incident",
        "cve", "jailbreak", "injection", "owasp", "mitigation"
    ],
    "QA": [
        "test strategy", "defect", "triage", "accessibility", "regression",
        "automation", "quality", "k6", "playwright", "test plan"
    ],
}

_TIER_MAP: dict[str, str] = {
    "developer": "balanced",
    "analyst": "balanced",
    "researcher": "powerful",
    "manager": "fast",
    "writer": "fast",
    "designer": "balanced",
    "IT": "balanced",
    "PM": "powerful",
    "EM": "balanced",
    "SM": "fast",
    "NTM": "fast",
    "Banking": "powerful",
    "Legal": "powerful",
    "Healthcare": "powerful",
    "HR": "balanced",
    "Data": "balanced",
    "CSuite": "powerful",
    "Security": "powerful",
    "QA": "balanced",
}

_EXPLANATION_PATTERN = re.compile(r'\b(explain|how does|what is|describe|clarify)\b', re.I)


class RoleIntelligence:
    def detect(self, text: str, explanation_mode: bool = False) -> RoleProfile:
        text_lower = text.lower()
        scores: dict[str, float] = {}

        for role, keywords in _ROLE_KEYWORDS.items():
            matched = [kw for kw in keywords if kw in text_lower]
            scores[role] = len(matched) / len(keywords)

        best_role = max(scores, key=lambda r: scores[r])
        confidence = min(1.0, scores[best_role] * 5)

        if confidence < 0.1:
            best_role = "developer"
            confidence = 0.3

        matched_kws = [kw for kw in _ROLE_KEYWORDS[best_role] if kw in text_lower]
        tier = _TIER_MAP.get(best_role, "balanced")

        context_hint = f"{best_role} context"
        if explanation_mode or _EXPLANATION_PATTERN.search(text):
            context_hint = f"explain mode — {best_role} context"

        return RoleProfile(
            role=best_role,
            confidence=round(confidence, 3),
            keywords_matched=matched_kws,
            recommended_model_tier=tier,
            context_hint=context_hint,
        )
