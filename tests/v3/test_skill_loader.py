"""Tests for SkillLoader."""

from pathlib import Path
import pytest
from promptwise_v3.core.skill_loader import SkillLoader


def test_load_skills(tmp_path):
    skill_file = tmp_path / "test-skill.md"
    skill_file.write_text("---\nname: test-skill\ndescription: A test skill\ntriggers:\n  - code\n---\nDo something")
    sl = SkillLoader(tmp_path)
    sl.load_skills()
    assert len(sl.skills) == 1
    assert "test-skill" in sl.skills


def test_skill_loader_empty_dir(tmp_path):
    sl = SkillLoader(tmp_path)
    sl.load_skills()
    assert len(sl.skills) == 0


def test_match_skill_by_trigger(tmp_path):
    skill_file = tmp_path / "test.md"
    skill_file.write_text("---\nname: code-review\ndescription: CR\ntriggers:\n  - review\n  - code\n---\nReview code")
    sl = SkillLoader(tmp_path)
    sl.load_skills()
    skill = sl.match_skill("please review my code")
    assert skill is not None
    assert skill.name == "code-review"


def test_get_skill(tmp_path):
    skill_file = tmp_path / "test.md"
    skill_file.write_text("---\nname: hello\ndescription: Hi\ntriggers: []\n---\nHello")
    sl = SkillLoader(tmp_path)
    sl.load_skills()
    skill = sl.get_skill("hello")
    assert skill is not None
    assert skill.description == "Hi"
