"""Corpus-level regression test for SkillLoader.match_skill() against the
REAL skill_packs/ directory -- not synthetic tmp_path skills. This closes the
gap flagged in the 2026-08-19 gap audit: the raw-length MIN_MATCH_SCORE floor
silently dropped ~22% of true-positive matches across the real corpus (short
but unique triggers like "deslop" or "debug"), while a specificity-based
confidence check (SkillLoader._collision_word_set()) still correctly rejects
matches built only from generic words shared across skills (the
agile-analyst/"research" case that motivated the original floor).
"""
from pathlib import Path

from promptwise.core.skill_loader import SkillLoader

_SKILL_PACKS_DIR = Path(__file__).resolve().parents[1] / "skill_packs"


def _loader() -> SkillLoader:
    loader = SkillLoader(_SKILL_PACKS_DIR)
    loader.load_skills()
    return loader


def test_real_corpus_loads():
    loader = _loader()
    assert len(loader.skills) > 0, "skill_packs/ did not load any skills"


def test_debug_crash_prompt_matches_systematic_debugging():
    match = _loader().match_skill("help me debug this crash")
    assert match is not None
    assert match.best.name == "systematic-debugging"


def test_deslop_prompt_matches_deslop():
    match = _loader().match_skill("deslop this text")
    assert match is not None
    assert match.best.name == "deslop"


def test_commit_message_prompt_matches_git_workflow():
    match = _loader().match_skill("write a commit message")
    assert match is not None
    assert match.best.name == "git-workflow"


def test_bare_research_does_not_match_agile_analyst():
    # Original gap-audit bug: a single generic word shared/collision-prone
    # across skills must not produce a confident match on its own.
    match = _loader().match_skill("research")
    if match is not None:
        assert match.best.name != "agile-analyst"
