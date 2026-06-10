import re

from promptwise_v3.types import RoleDetectionResult

_ROLES = {
    "developer": {
        "keywords": ["refactor", "debug", "code", "function", "api", "bug", "fix", "test", "import", "class", "method", "variable", "implement"],
        "patterns": [r"def\s+\w+", r"class\s+\w+", r"import\s+", r"function\s+"],
        "weight": 1.0,
        "tier": "balanced",
    },
    "analyst": {
        "keywords": ["metrics", "data", "report", "trend", "average", "sum", "count", "compare", "analyze", "dashboard", "chart", "sql"],
        "patterns": [r"SELECT\s+", r"GROUP BY", r"WHERE"],
        "weight": 0.95,
        "tier": "balanced",
    },
    "manager": {
        "keywords": ["timeline", "roadmap", "prioritize", "capacity", "velocity", "sprint", "plan", "stakeholder", "milestone", "deadline", "budget", "resource"],
        "patterns": [r"Q[1-4]\s+20\d{2}", r"milestone"],
        "weight": 0.90,
        "tier": "fast",
    },
    "security": {
        "keywords": ["auth", "encrypt", "vulnerability", "compliance", "pii", "threat", "risk", "secure", "breach", "cve", "owasp", "injection"],
        "patterns": [r"CVE-\d+", r"OWASP", r"GDPR"],
        "weight": 1.0,
        "tier": "powerful",
    },
    "IT": {
        "keywords": ["deploy", "infra", "cloud", "kubernetes", "docker", "terraform", "server", "network", "container", "devops", "aws", "pipeline"],
        "patterns": [r"kubectl", r"docker\s+run", r"terraform\s+"],
        "weight": 0.98,
        "tier": "balanced",
    },
    "designer": {
        "keywords": ["ui", "ux", "design", "layout", "component", "interface", "visual", "responsive", "accessibility", "wireframe", "prototype"],
        "patterns": [r"css\s+", r"design\s+system"],
        "weight": 0.9,
        "tier": "balanced",
    },
    "writer": {
        "keywords": ["write", "content", "article", "blog", "copy", "document", "narrative", "style", "tone", "draft", "edit", "publish"],
        "patterns": [r"blog\s+post", r"article"],
        "weight": 0.85,
        "tier": "fast",
    },
    "researcher": {
        "keywords": ["research", "study", "evidence", "experiment", "hypothesis", "methodology", "finding", "conclusion", "cite", "source", "academic"],
        "patterns": [r"research\s+", r"study\s+"],
        "weight": 0.9,
        "tier": "powerful",
    },
    "pm": {
        "keywords": ["product", "feature", "requirement", "user story", "backlog", "roadmap", "launch", "market", "customer", "spec"],
        "patterns": [r"user\s+story", r"acceptance\s+criteria"],
        "weight": 0.88,
        "tier": "powerful",
    },
    "legal": {
        "keywords": ["legal", "contract", "agreement", "compliance", "liability", "ip", "patent", "trademark", "copyright", "gdpr", "ccpa"],
        "patterns": [r"GDPR", r"CCPA", r"contract"],
        "weight": 0.95,
        "tier": "powerful",
    },
    "data": {
        "keywords": ["database", "sql", "etl", "pipeline", "query", "schema", "indexing", "optimization", "warehouse", "analytics"],
        "patterns": [r"SELECT\s+", r"INDEX", r"EXPLAIN"],
        "weight": 0.92,
        "tier": "balanced",
    },
    "qa": {
        "keywords": ["test", "qa", "quality", "defect", "automation", "coverage", "bug", "regression", "playwright", "pytest"],
        "patterns": [r"test\s+", r"automation"],
        "weight": 0.9,
        "tier": "balanced",
    },
    "executive": {
        "keywords": ["strategic", "roi", "business", "market", "growth", "revenue", "board", "investor", "vision", "competitive"],
        "patterns": [r"ROI", r"board\s+"],
        "weight": 0.85,
        "tier": "fast",
    },
    "healthcare": {
        "keywords": ["hipaa", "patient", "clinical", "medical", "diagnosis", "treatment", "fhir", "hl7", "health", "disease"],
        "patterns": [r"HIPAA", r"FHIR", r"HL7"],
        "weight": 0.95,
        "tier": "powerful",
    },
    "finance": {
        "keywords": ["finance", "banking", "finra", "basel", "aml", "trading", "investment", "portfolio", "risk", "regulation", "audit"],
        "patterns": [r"FINRA", r"Basel", r"AML"],
        "weight": 0.95,
        "tier": "powerful",
    },
    "hr": {
        "keywords": ["hiring", "interview", "onboarding", "compensation", "people", "performance review", "recruitment", "talent", "job description"],
        "patterns": [r"job\s+description", r"interview"],
        "weight": 0.85,
        "tier": "balanced",
    },
}


class RoleDetector:
    def __init__(self, roles_config: dict | None = None):
        self.roles_config = roles_config or _ROLES

    def detect(self, prompt: str, context: dict | None = None) -> RoleDetectionResult:
        context = context or {}
        prompt_lower = prompt.lower()
        tokens = set(prompt_lower.split())

        scores: dict[str, tuple[float, list[str]]] = {}

        for role_name, role_config in self.roles_config.items():
            score = 0.0
            matched_keywords: list[str] = []

            for keyword in role_config.get("keywords", []):
                for token in tokens:
                    if keyword in token:
                        score += 1.0
                        matched_keywords.append(keyword)
                        break

            for pattern in role_config.get("patterns", []):
                try:
                    if re.search(pattern, prompt_lower, re.IGNORECASE):
                        score += 2.0
                        matched_keywords.append(f"pattern:{pattern}")
                except re.error:
                    pass

            file_type = context.get("file_type", "")
            if file_type and self._file_type_match(role_name, file_type):
                score += 1.5

            score = (score / 1.38) * role_config.get("weight", 1.0)
            scores[role_name] = (score, matched_keywords)

        ranked = sorted(scores.items(), key=lambda x: x[1][0], reverse=True)

        if not ranked:
            return RoleDetectionResult(primary_role="general", confidence=0.0, secondary_roles=[], keywords_matched=[], rationale="No role signals detected")

        primary_role, (primary_score, primary_keywords) = ranked[0]
        primary_confidence = min(1.0, primary_score)

        secondaries = [(role, score) for role, (score, _) in ranked[1:4] if score > 0]

        if primary_confidence > 0.5:
            rationale = f"Detected {primary_role} role ({primary_confidence:.0%} confidence) from {len(primary_keywords)} keywords"
        else:
            rationale = f"Weak signal for {primary_role} ({primary_confidence:.0%} confidence)"

        return RoleDetectionResult(
            primary_role=primary_role,
            confidence=primary_confidence,
            secondary_roles=secondaries,
            keywords_matched=list(set(primary_keywords))[:5],
            rationale=rationale,
        )

    def _file_type_match(self, role: str, file_type: str) -> bool:
        mapping = {"py": "developer", "js": "developer", "ts": "developer", "sql": "data",
                   "yaml": "IT", "docker": "IT", "md": "writer", "csv": "analyst", "json": "data"}
        return mapping.get(file_type) == role

    def get_recommended_tier(self, role: str) -> str:
        cfg = self.roles_config.get(role, {})
        return cfg.get("tier", "balanced")
