"""All 63 skill packs must have valid frontmatter, unique names, and load."""
import re
import pathlib

import yaml

from promptwise.core import SkillLoader

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKS = sorted((ROOT / "skill_packs").rglob("*.md"))


def test_packs_exist():
    assert len(PACKS) >= 63


def test_every_pack_has_required_frontmatter():
    problems = []
    for f in PACKS:
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", f.read_text(encoding="utf-8"), re.DOTALL)
        assert m, f"{f.name}: no frontmatter"
        meta = yaml.safe_load(m.group(1)) or {}
        for req in ("name", "description", "triggers"):
            if not meta.get(req):
                problems.append(f"{f.name}: missing {req}")
        if len(m.group(2).strip()) < 40:
            problems.append(f"{f.name}: body too short")
    assert not problems, problems


def test_names_unique():
    names = []
    for f in PACKS:
        m = re.match(r"^---\s*\n(.*?)\n---", f.read_text(encoding="utf-8"), re.DOTALL)
        names.append((yaml.safe_load(m.group(1)) or {}).get("name"))
    dups = {n for n in names if names.count(n) > 1}
    assert not dups, f"duplicate skill names: {dups}"


def test_all_load_via_loader():
    sl = SkillLoader(ROOT / "skill_packs")
    sl.load_skills()
    assert len(sl.skills) == len(PACKS)
