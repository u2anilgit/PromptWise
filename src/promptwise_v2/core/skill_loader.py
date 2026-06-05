import logging
import os
import re
import yaml
import jsonschema
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str]
    depends_on: list[str]
    output_schema: dict | None
    roles: list[str]
    model_tier: str
    system_prompt: str
    raw_content: str


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
                    file_path = Path(root) / file
                    try:
                        self._load_skill_file(file_path)
                    except Exception as e:
                        logging.warning(f"Error loading skill file {file_path}: {e}")

    def _load_skill_file(self, file_path: Path) -> None:
        content = file_path.read_text(encoding="utf-8")

        # Extract YAML frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return

        frontmatter_text = match.group(1)
        markdown_text = match.group(2)

        metadata = yaml.safe_load(frontmatter_text)
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
            system_prompt=markdown_text.strip(),
            raw_content=content,
        )
        self.skills[skill.name] = skill

    def get_skill(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def match_skill(self, text: str, role: str) -> Skill | None:
        text_lower = text.lower()
        best_match = None
        max_score = 0

        for skill in self.skills.values():
            if skill.roles and role not in skill.roles:
                continue

            score = 0
            for trigger in skill.triggers:
                if trigger.lower() in text_lower:
                    score += len(trigger)

            if score > max_score:
                max_score = score
                best_match = skill

        if max_score > 0:
            return best_match
        return None

    def validate_output(self, skill_name: str, output_data: dict) -> bool:
        skill = self.get_skill(skill_name)
        if not skill or not skill.output_schema:
            return True
        try:
            jsonschema.validate(instance=output_data, schema=skill.output_schema)
            return True
        except jsonschema.ValidationError:
            return False
