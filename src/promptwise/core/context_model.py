"""Builds a lightweight project context model from prompt text and a repo scan.

Combines intent (from Router), role (from RoleDetector), detected tech stack
(from repo marker files), and regulatory domain (from text keywords). All
detection is best-effort and resilient: nothing here raises on bad input or a
missing repo_root.
"""
from dataclasses import dataclass, field
from pathlib import Path

from promptwise.core.role_detector import RoleDetector
from promptwise.core.router import Router

# marker file -> stack label
_STACK_MARKERS: dict[str, str] = {
    "package.json": "node",
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
}

# (domain, regulated) keyed by keyword found in lowercased text
_DOMAIN_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("banking", "finance", "payment", "aml", "finra"), "banking"),
    (("health", "hipaa", "phi", "fhir", "clinical"), "healthcare"),
    (("legal", "gdpr", "contract"), "legal"),
]

_REGULATED_DOMAINS = {"banking", "healthcare", "legal"}


@dataclass
class ProjectContextModel:
    intent: str
    role: str | None
    stack: list[str] = field(default_factory=list)
    domain: str | None = None
    regulated: bool = False


def _detect_intent(text: str) -> str:
    try:
        return Router()._detect_intent(text) or "auto"
    except Exception:
        return "auto"


def _detect_role(text: str) -> str | None:
    try:
        result = RoleDetector().detect(text)
        role = getattr(result, "primary_role", None)
        if not role or role == "general":
            return None
        return role
    except Exception:
        return None


def _detect_stack(repo_root: str | Path) -> list[str]:
    try:
        root = Path(repo_root)
        if not root.is_dir():
            return []
        labels: set[str] = set()
        for marker, label in _STACK_MARKERS.items():
            if (root / marker).is_file():
                labels.add(label)
        return sorted(labels)
    except Exception:
        return []


def _detect_domain(text: str) -> tuple[str | None, bool]:
    t = (text or "").lower()
    for keywords, domain in _DOMAIN_KEYWORDS:
        if any(kw in t for kw in keywords):
            return domain, domain in _REGULATED_DOMAINS
    return None, False


def build_context_model(text: str, repo_root: str | Path = ".") -> ProjectContextModel:
    """Build a ProjectContextModel from prompt text and a read-only repo scan."""
    domain, regulated = _detect_domain(text)
    return ProjectContextModel(
        intent=_detect_intent(text),
        role=_detect_role(text),
        stack=_detect_stack(repo_root),
        domain=domain,
        regulated=regulated,
    )
