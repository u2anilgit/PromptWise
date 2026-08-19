import sys
import textwrap
from pathlib import Path

# repo_root/scripts is not a package the src-layout conftest.py puts on
# sys.path (that conftest only prepends <worktree>/src, for `promptwise`
# itself) -- under the full suite's collection order this makes
# `scripts.lint_skill_triggers` unimportable even though it resolves fine
# when this file is run standalone, the same class of ambient-sys.path
# fragility conftest.py's own docstring warns about for worktrees. Insert
# the repo root explicitly rather than depend on incidental cwd insertion.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lint_skill_triggers import find_collisions


def _write_skill(dir_: Path, name: str, triggers: list[str]) -> None:
    triggers_yaml = "[" + ", ".join(f'"{t}"' for t in triggers) + "]"
    (dir_ / f"{name}.md").write_text(textwrap.dedent(f"""\
        ---
        name: {name}
        description: "test skill"
        triggers: {triggers_yaml}
        ---
        body
        """), encoding="utf-8")


def test_finds_generic_word_collision(tmp_path):
    _write_skill(tmp_path, "a", ["research", "analyst"])
    _write_skill(tmp_path, "b", ["research", "codebase audit"])

    collisions = find_collisions(tmp_path)

    keys = {tuple(sorted(c["skills"])) for c in collisions}
    assert ("a", "b") in keys
    matched = next(c for c in collisions if sorted(c["skills"]) == ["a", "b"])
    assert matched["keys"] == ["research"]


def test_no_collision_for_distinct_triggers(tmp_path):
    _write_skill(tmp_path, "a", ["project brief", "problem framing"])
    _write_skill(tmp_path, "b", ["cost report", "budget"])

    assert find_collisions(tmp_path) == []


def test_multiword_phrases_excluded_from_collision_scan(tmp_path):
    _write_skill(tmp_path, "a", ["cost report"])
    _write_skill(tmp_path, "b", ["cost report"])

    # multi-word phrases are excluded even if identical -- collisions there
    # are vanishingly unlikely to be accidental and out of scope for this lint
    assert find_collisions(tmp_path) == []
