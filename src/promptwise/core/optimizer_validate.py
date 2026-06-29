"""optimizer_validate — deterministic, OFFLINE quality scorer for SKILL.md packs.

The Phase 3 plan assumed the existing ``skill_validator`` could score a SKILL.md,
but that module only validates a tool's JSON output against a JSON Schema. There
was no SKILL.md quality signal in the repo. This is that missing piece: a
transparent heuristic score (0-100) so the optimizer can accept a patch only when
it strictly improves the pack. No model, no network — purely structural.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
# count rules inside PromptWise's managed learned-rules region
_RULE_LINE = re.compile(r"^\s*-\s+.+->.+$", re.MULTILINE)


@dataclass
class SkillScore:
    score: int = 0
    valid: bool = False
    breakdown: dict = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict:
        return {"score": self.score, "valid": self.valid,
                "breakdown": dict(self.breakdown), "reason": self.reason}


def parse_skill(content: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Empty dict if no parseable frontmatter."""
    m = _FRONTMATTER_RE.match(content or "")
    if not m:
        return {}, content or ""
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, m.group(2)


def validate_skill(content: str) -> tuple[bool, str]:
    """Structural validity: frontmatter parses and carries a name (the same
    contract SkillLoader enforces before a pack is loadable)."""
    meta, _ = parse_skill(content)
    if not meta:
        return False, "missing or unparseable frontmatter"
    if "name" not in meta:
        return False, "frontmatter missing 'name'"
    return True, "ok"


def score_skill(content: str) -> SkillScore:
    meta, body = parse_skill(content)
    valid, reason = validate_skill(content)
    bd: dict = {}

    bd["name"] = 15 if meta.get("name") else 0
    desc = str(meta.get("description", ""))
    bd["description"] = 15 if desc else 0
    bd["description_len"] = 10 if 20 <= len(desc) <= 400 else 0
    bd["triggers"] = 15 if meta.get("triggers") else 0

    headings = len(re.findall(r"^#{1,6}\s+\S", body, re.MULTILINE))
    bd["headings"] = min(10, headings * 5)

    bullets = len(re.findall(r"^\s*[-*]\s+\S", body, re.MULTILINE))
    bd["bullets"] = min(15, bullets * 3)

    bd["actionable"] = 10 if ("->" in body or re.search(r"(?i)\bexample\b", body)) else 0
    bd["body_len"] = 10 if len(body.strip()) >= 200 else 0

    # reward encoded corrections: each learned "mistake -> fix" rule is signal
    rules = len(_RULE_LINE.findall(body))
    bd["learned_rules"] = min(20, rules * 5)

    total = min(100, sum(bd.values()))
    return SkillScore(score=total, valid=valid, breakdown=bd,
                      reason=reason if not valid else "")
