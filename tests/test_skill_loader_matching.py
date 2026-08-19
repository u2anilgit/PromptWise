from pathlib import Path

from promptwise.core.skill_loader import SkillLoader


def _write_skill(dir_: Path, name: str, triggers: list[str], desc: str = "test") -> None:
    triggers_yaml = "[" + ", ".join(f'"{t}"' for t in triggers) + "]"
    (dir_ / f"{name}.md").write_text(
        f'---\nname: {name}\ndescription: "{desc}"\ntriggers: {triggers_yaml}\n---\nbody\n',
        encoding="utf-8",
    )


def test_collision_only_match_returns_none(tmp_path):
    # Both skills share the single-word trigger "research" -- neither skill
    # has any unique trigger backing this particular match, so it's the
    # "research" -> agile-analyst gap-audit bug case: too weak to report.
    _write_skill(tmp_path, "a", ["research"])
    _write_skill(tmp_path, "b", ["research"])
    loader = SkillLoader(tmp_path)
    loader.load_skills()

    assert loader.match_skill("please do some research today") is None


def test_short_unique_trigger_is_confident(tmp_path):
    # A short trigger (6 chars) that is NOT shared with any other skill
    # should match confidently -- specificity, not raw length, is the
    # confidence signal.
    _write_skill(tmp_path, "deslop", ["deslop"])
    loader = SkillLoader(tmp_path)
    loader.load_skills()

    match = loader.match_skill("please deslop this text")

    assert match is not None
    assert match.best.name == "deslop"


def test_clear_winner_has_no_contenders(tmp_path):
    _write_skill(tmp_path, "a", ["cost report"])
    _write_skill(tmp_path, "b", ["zz"])
    loader = SkillLoader(tmp_path)
    loader.load_skills()

    match = loader.match_skill("please generate a cost report")

    assert match.best.name == "a"
    assert match.contenders == []


def test_near_tie_surfaces_both_contenders(tmp_path):
    _write_skill(tmp_path, "a", ["project brief"])
    _write_skill(tmp_path, "b", ["problem framing"])  # same length, both present
    loader = SkillLoader(tmp_path)
    loader.load_skills()

    match = loader.match_skill("need a project brief and problem framing")

    assert match.best is not None
    assert any(c.name in ("a", "b") and c.name != match.best.name for c in match.contenders)
