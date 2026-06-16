import logging
import os
import re
import yaml

from pathlib import Path

from promptwise.types import Skill


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self.skills: dict[str, Skill] = {}

    def load_skills(self) -> None:
        if not self.skills_dir.exists():
            return
        for root, _, files in os.walk(self.skills_dir):
            for file in files:
                if file.endswith(".md"):
                    try:
                        self._load_skill_file(Path(root) / file)
                    except Exception as e:
                        logging.warning(f"Error loading skill {file}: {e}")

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

    def match_skill(self, text: str, role: str = "") -> Skill | None:
        text_lower = text.lower()
        best = None
        max_score = 0
        for skill in self.skills.values():
            if skill.roles and role and role not in skill.roles:
                continue
            score = sum(len(t) for t in skill.triggers if t.lower() in text_lower)
            if score > max_score:
                max_score = score
                best = skill
        return best if max_score > 0 else None
