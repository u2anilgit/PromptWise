from pathlib import Path

from promptwise.core.skill_loader import SkillLoader, MIN_MATCH_SCORE


def _write_skill(dir_: Path, name: str, triggers: list[str], desc: str = "test") -> None:
    triggers_yaml = "[" + ", ".join(f'"{t}"' for t in triggers) + "]"
    (dir_ / f"{name}.md").write_text(
        f'---\nname: {name}\ndescription: "{desc}"\ntriggers: {triggers_yaml}\n---\nbody\n',
        encoding="utf-8",
    )


def test_below_floor_score_returns_none(tmp_path):
    _write_skill(tmp_path, "a", ["xy"])  # score 2, below any sane floor
    loader = SkillLoader(tmp_path)
    loader.load_skills()

    assert loader.match_skill("please look at xy today") is None


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
