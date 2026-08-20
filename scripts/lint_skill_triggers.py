"""lint_skill_triggers -- finds skill_pack triggers that collide on a single
generic word, the failure mode that misrouted a plain research/investigation
prompt to `agile-analyst` (whose triggers list included the bare word
"research") in the 2026-08-19 gap audit. `SkillLoader.match_skill()` scores
skills by summed matched-keyword length with no confidence floor, so any
short single-word trigger shared loosely across the domain can win on an
unrelated prompt. This script is a standalone dev-time lint, not wired into
the server -- run it after adding/editing a skill pack's triggers.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import yaml

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_MAX_GENERIC_LEN = 12


def _load_triggers(skills_dir: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in sorted(skills_dir.rglob("*.md")):
        match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not match:
            continue
        meta = yaml.safe_load(match.group(1)) or {}
        name = meta.get("name")
        if not name:
            continue
        out[name] = meta.get("triggers", []) or []
    return out


def find_collisions(skills_dir: Path) -> list[dict]:
    """Return collisions where 2+ skills share a single-word trigger of
    _MAX_GENERIC_LEN characters or fewer (the generic-word case that's easy
    to type into a skill's triggers list without noticing it's already
    claimed elsewhere). Multi-word phrase triggers are excluded -- they're
    specific enough that an accidental collision is not the realistic risk.
    """
    by_key: dict[str, set[str]] = defaultdict(set)
    for skill_name, triggers in _load_triggers(skills_dir).items():
        for trigger in triggers:
            key = trigger.strip().lower()
            if " " in key or len(key) > _MAX_GENERIC_LEN:
                continue
            by_key[key].add(skill_name)

    collisions = []
    seen_pairs: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for key, skills in by_key.items():
        if len(skills) < 2:
            continue
        seen_pairs[tuple(sorted(skills))].append(key)

    for skills, keys in seen_pairs.items():
        collisions.append({"keys": sorted(keys), "skills": list(skills)})
    return collisions


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "skill_packs"
    collisions = find_collisions(root)
    if not collisions:
        print("No generic-word trigger collisions found.")
        return 0
    print(f"Found {len(collisions)} generic-word trigger collision group(s):")
    for c in collisions:
        print(f"  {c['keys']} shared by: {', '.join(c['skills'])}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
