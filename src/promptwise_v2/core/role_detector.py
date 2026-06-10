"""
Automatic role detection from prompt context.

Infers user role (developer, analyst, manager, etc.) from prompt keywords
and patterns, enabling context-aware prompt optimization.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Dict, Set, Optional


@dataclass
class RoleDetectionResult:
    """Result of role detection analysis."""

    primary_role: str
    confidence: float  # 0.0-1.0
    secondary_roles: List[Tuple[str, float]]
    keywords_matched: List[str]
    rationale: str


class RoleDetector:
    """
    Detect user role from prompt context.

    Uses keyword matching + pattern matching to infer role.
    No external ML or API calls; fast (< 100ms).
    """

    def __init__(self, roles_config: Dict[str, Dict] = None):
        """
        Initialize detector.

        Args:
            roles_config: Optional pre-built role config. If None, uses defaults.
        """
        self.roles_config = roles_config or self._get_default_roles()
        self.role_keywords: Dict[str, Dict] = {}
        self._build_keyword_index()

    def _get_default_roles(self) -> Dict[str, Dict]:
        """Get default role configuration."""
        return {
            "developer": {
                "keywords": ["refactor", "debug", "code", "function", "api", "library",
                            "bug", "issue", "fix", "test", "import", "module",
                            "method", "variable", "loop", "condition", "error"],
                "patterns": [r"def\s+\w+", r"class\s+\w+", r"import\s+", r"function\s+"],
                "weight": 1.0
            },
            "analyst": {
                "keywords": ["metrics", "data", "report", "trend", "aggregat", "average",
                            "sum", "count", "compare", "analyze", "pivot", "dashboard",
                            "chart", "graph", "query", "sql", "database"],
                "patterns": [r"SELECT\s+", r"aggregat", r"GROUP BY", r"WHERE"],
                "weight": 0.95
            },
            "manager": {
                "keywords": ["timeline", "roadmap", "priorit", "capacity", "velocity",
                            "sprint", "plan", "stakeholder", "decision", "strategy",
                            "milestone", "deadline", "budget", "resource"],
                "patterns": [r"Q[1-4]\s+20\d{2}", r"week\s+\d+", r"milestone"],
                "weight": 0.90
            },
            "security": {
                "keywords": ["auth", "encrypt", "vulnerability", "compliance", "gdpr",
                            "ccpa", "pii", "threat", "risk", "penetrat", "exploit",
                            "secure", "hack", "breach", "ssl", "tls", "certificate"],
                "patterns": [r"CVE-\d+", r"OWASP", r"secure", r"password", r"GDPR"],
                "weight": 1.0
            },
            "IT": {
                "keywords": ["deploy", "infra", "scaling", "failover", "cloud", "aws",
                            "kubernetes", "docker", "ci/cd", "terraform", "ansible",
                            "server", "network", "vm", "container", "devops"],
                "patterns": [r"kubectl", r"docker\s+run", r"terraform\s+", r"aws\s+"],
                "weight": 0.98
            },
            "designer": {
                "keywords": ["ui", "ux", "design", "layout", "component", "interface",
                            "visual", "responsive", "accessibility", "color", "font",
                            "style", "theme", "wireframe", "prototype", "experience"],
                "patterns": [r"css\s+", r"design\s+system", r"figma"],
                "weight": 0.9
            },
            "writer": {
                "keywords": ["write", "content", "article", "blog", "copy", "document",
                            "narrative", "storytell", "prose", "style", "tone", "draft",
                            "edit", "publish"],
                "patterns": [r"blog\s+post", r"article", r"essay"],
                "weight": 0.85
            },
            "researcher": {
                "keywords": ["research", "study", "evidence", "experiment", "hypothesis",
                            "methodology", "data", "analysis", "finding", "conclusion",
                            "cite", "source", "academic"],
                "patterns": [r"research\s+", r"study\s+", r"experiment"],
                "weight": 0.9
            },
            "pm": {
                "keywords": ["product", "feature", "requirement", "user", "story", "epic",
                            "backlog", "roadmap", "launch", "market", "customer",
                            "stakeholder", "spec"],
                "patterns": [r"user\s+story", r"acceptance\s+criteria", r"epic"],
                "weight": 0.88
            },
            "legal": {
                "keywords": ["legal", "contract", "agreement", "compliance", "gdpr",
                            "ccpa", "liability", "risk", "ip", "patent", "trademark",
                            "lawsuit", "copyright"],
                "patterns": [r"GDPR", r"CCPA", r"contract", r"agreement"],
                "weight": 0.95
            },
            "healthcare": {
                "keywords": ["healthcare", "hipaa", "patient", "clinical", "medical",
                            "diagnosis", "treatment", "fhir", "hl7", "privacy",
                            "health", "disease"],
                "patterns": [r"HIPAA", r"FHIR", r"HL7"],
                "weight": 0.95
            },
            "finance": {
                "keywords": ["finance", "banking", "finra", "basel", "aml", "compliance",
                            "trading", "investment", "portfolio", "risk", "regulation",
                            "audit"],
                "patterns": [r"FINRA", r"Basel", r"AML"],
                "weight": 0.95
            },
            "data": {
                "keywords": ["database", "sql", "etl", "pipeline", "data", "warehouse",
                            "query", "schema", "indexing", "optimization", "tuning",
                            "performance"],
                "patterns": [r"SELECT\s+", r"INDEX", r"EXPLAIN"],
                "weight": 0.92
            },
            "qassurance": {
                "keywords": ["test", "qa", "quality", "defect", "automation", "coverage",
                            "bug", "regression", "acceptance", "manual", "playwright"],
                "patterns": [r"test\s+", r"automation", r"pytest", r"playwright"],
                "weight": 0.9
            },
            "executive": {
                "keywords": ["strategic", "roi", "business", "market", "competitive",
                            "growth", "revenue", "profit", "board", "investor",
                            "stakeholder", "vision"],
                "patterns": [r"ROI", r"board\s+", r"investor"],
                "weight": 0.85
            },
        }

    def _build_keyword_index(self) -> None:
        """Build keyword index from config."""
        self.role_keywords = self.roles_config.copy()

    def detect(self, prompt: str, context: Optional[Dict] = None) -> RoleDetectionResult:
        """
        Detect role from prompt.

        Args:
            prompt: User prompt text
            context: Optional context dict with:
                - file_type: 'sql', 'py', 'yaml', 'md', etc.
                - project_type: 'api', 'ml', 'infra', 'data', etc.
                - recent_roles: [previous role names]

        Returns:
            RoleDetectionResult with primary + secondary roles
        """
        context = context or {}
        prompt_lower = prompt.lower()
        tokens = set(prompt_lower.split())

        # Score each role
        scores: Dict[str, Tuple[float, List[str]]] = {}
        stopwords = {"is", "the", "to", "and", "a", "in", "for", "by", "on", "at", "with", "of", "it", "this", "that", "your", "my"}

        for role_name, role_config in self.role_keywords.items():
            score = 0.0
            matched_keywords: List[str] = []

            # Keyword matching
            for keyword in role_config.get("keywords", []):
                # Check if keyword appears in any token
                for token in tokens:
                    if keyword in token:
                        score += 1.0
                        matched_keywords.append(keyword)
                        break  # Count keyword once

            # Pattern matching (regex)
            for pattern in role_config.get("patterns", []):
                try:
                    if re.search(pattern, prompt_lower, re.IGNORECASE):
                        score += 2.0  # Patterns weighted higher
                        matched_keywords.append(f"pattern:{pattern}")
                except re.error:
                    pass

            # Boost from context
            if "file_type" in context:
                file_type = context["file_type"].lower()
                if self._is_file_type_match(role_name, file_type):
                    score += 1.5

            # Normalize score against a reasonable maximum matched keywords
            score = (score / 1.38) * role_config.get("weight", 1.0)

            scores[role_name] = (score, matched_keywords)

        # Rank by score
        ranked = sorted(scores.items(), key=lambda x: x[1][0], reverse=True)

        if not ranked:
            return RoleDetectionResult(
                primary_role="general",
                confidence=0.0,
                secondary_roles=[],
                keywords_matched=[],
                rationale="No role signals detected"
            )

        # Extract primary role
        primary_role, (primary_score, primary_keywords) = ranked[0]
        primary_confidence = min(1.0, primary_score)

        # Extract secondary roles (top 2-3 with score > 0)
        secondaries = [
            (role, score)
            for role, (score, _) in ranked[1:4]
            if score > 0
        ]

        # Build rationale
        if primary_confidence > 0.5:
            rationale = f"Detected {primary_role} role ({primary_confidence:.0%} confidence) from {len(primary_keywords)} keywords"
        else:
            rationale = f"Weak signal for {primary_role} ({primary_confidence:.0%} confidence); consider manual role selection"

        return RoleDetectionResult(
            primary_role=primary_role,
            confidence=primary_confidence,
            secondary_roles=secondaries,
            keywords_matched=list(set(primary_keywords))[:5],  # Top 5 unique
            rationale=rationale
        )

    def _is_file_type_match(self, role: str, file_type: str) -> bool:
        """Check if file type suggests a role."""
        file_role_map = {
            "py": "developer",
            "js": "developer",
            "ts": "developer",
            "sql": "data",
            "yaml": "IT",
            "docker": "IT",
            "md": "writer",
            "csv": "analyst",
            "json": "data",
        }
        return file_role_map.get(file_type) == role

    def apply_role_to_prompt(self, prompt: str, role: str, role_prefixes: Dict[str, str]) -> str:
        """
        Prepend role prefix to prompt.

        Args:
            prompt: Original prompt
            role: Role name
            role_prefixes: Dict of role -> prefix string

        Returns:
            Modified prompt with prefix
        """
        if role in role_prefixes and role_prefixes[role]:
            prefix = role_prefixes[role]
            return f"{prefix}\n\n{prompt}"
        return prompt


__all__ = ["RoleDetector", "RoleDetectionResult"]
