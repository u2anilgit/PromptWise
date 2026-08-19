import logging
import os
import re
import yaml

from dataclasses import dataclass
from pathlib import Path

from promptwise.core.text_match import contains_keyword
from promptwise.types import Skill

# Confidence is judged by specificity, not raw trigger length: a match is
# confident only if at least one of its matched triggers is NOT shared with
# any other loaded skill. This mirrors scripts/lint_skill_triggers.py's
# find_collisions() -- same single-word/<=12-char/no-space filter -- so a
# skill whose entire matched-trigger set is generic words shared across 2+
# skills (e.g. agile-analyst's bare "research", the 2026-08-19 gap audit
# case) is rejected, while a short-but-unique trigger (e.g. deslop's own
# 6-char name) is accepted regardless of length.
_MAX_GENERIC_TRIGGER_LEN = 12

# Any other skill scoring within this fraction of the top score is reported
# as a contender instead of being silently discarded by scan order.
NEAR_TIE_RATIO = 0.85


@dataclass
class SkillMatch:
    best: "Skill"
    score: int
    contenders: list["Skill"]


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self.skills: dict[str, Skill] = {}
        self._collision_triggers: set[str] | None = None

    def load_skills(self) -> None:
        # Loading (or reloading) skills invalidates any cached collision set
        # -- it's derived from self.skills and must be recomputed lazily.
        self._collision_triggers = None
        if not self.skills_dir.exists():
            return
        for root, _, files in os.walk(self.skills_dir):
            for file in files:
                if file.endswith(".md"):
                    try:
                        self._load_skill_file(Path(root) / file)
                    except Exception as e:
                        logging.warning(f"Error loading skill {file}: {e}")

    def _collision_word_set(self) -> set[str]:
        """Single-word/<=12-char triggers shared by 2+ skills -- the same
        collision signal scripts/lint_skill_triggers.py's find_collisions()
        computes, ported here (not imported) to avoid src/ depending on a
        repo-root dev script."""
        if self._collision_triggers is not None:
            return self._collision_triggers
        owners: dict[str, set[str]] = {}
        for skill in self.skills.values():
            for trigger in skill.triggers:
                key = trigger.strip().lower()
                if " " in key or len(key) > _MAX_GENERIC_TRIGGER_LEN:
                    continue
                owners.setdefault(key, set()).add(skill.name)
        self._collision_triggers = {key for key, names in owners.items() if len(names) >= 2}
        return self._collision_triggers

    def _load_skill_file(self, file_path: Path) -> None:
        content = file_path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return
        metadata = yaml.safe_load(match.group(1))
        if not metadata or "name" not in metadata:
            return
        skill = Skill(
            name=metadata["name"],
            description=metadata.get("description", ""),
            triggers=metadata.get("triggers", []),
            depends_on=metadata.get("depends_on", []),
            output_schema=metadata.get("output_schema"),
            roles=metadata.get("roles", []),
            model_tier=metadata.get("model_tier", "auto"),
            system_prompt=match.group(2).strip(),
            raw_content=content,
        )
        self.skills[skill.name] = skill

    def get_skill(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def match_skill(self, text: str, role: str = "") -> SkillMatch | None:
        text_lower = text.lower()
        collisions = self._collision_word_set()
        scored: list[tuple[int, bool, Skill]] = []
        for skill in self.skills.values():
            if skill.roles and role and role not in skill.roles:
                continue
            matched = [t for t in skill.triggers if contains_keyword(text_lower, t.lower())]
            if not matched:
                continue
            score = sum(len(t) for t in matched)
            # Confident iff at least one matched trigger is NOT shared with
            # another skill -- a skill matched only on collision-shared
            # generic words is too weak to report.
            confident = any(t.strip().lower() not in collisions for t in matched)
            scored.append((score, confident, skill))

        if not scored:
            return None
        scored.sort(key=lambda triple: triple[0], reverse=True)
        top_score, top_confident, best = scored[0]
        if not top_confident:
            return None

        contenders = [
            skill for score, _, skill in scored[1:]
            if score >= top_score * NEAR_TIE_RATIO
        ]
        return SkillMatch(best=best, score=top_score, contenders=contenders)
