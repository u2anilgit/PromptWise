"""Phase 3 — offline skill auto-optimization: scorer + reflect/patch/validate/accept."""
import asyncio
import json

from promptwise.core.optimizer_validate import score_skill, validate_skill, parse_skill
from promptwise.core.skill_optimizer import optimize_skill_pack, _merge_skill_block
from promptwise.core.learning_store import LearningStore

SKILL = """---
name: demo-pack
description: A demo skill pack used for optimizer tests with enough description text.
triggers: [demo, test]
---

# Demo Pack

Some guidance prose here that is reasonably long so the body length component
of the score is satisfied for the baseline measurement of this example pack.

## Steps
- do the thing
- verify the thing
"""


# ── scorer / validator ───────────────────────────────────────────────────────
def test_score_valid_skill():
    s = score_skill(SKILL)
    assert s.valid and s.score > 0
    assert s.breakdown["name"] == 15 and s.breakdown["triggers"] == 15


def test_validate_rejects_no_frontmatter():
    ok, why = validate_skill("# just a heading\nno frontmatter")
    assert not ok and "frontmatter" in why


def test_parse_skill_roundtrip():
    meta, body = parse_skill(SKILL)
    assert meta["name"] == "demo-pack" and "Demo Pack" in body


def test_learned_rules_raise_score():
    base = score_skill(SKILL).score
    patched = _merge_skill_block(SKILL, "<!-- promptwise:managed:start v=1 hash=abc -->\n"
                                 "## Learned rules (PromptWise-managed)\n"
                                 "- used eval -> use ast.literal_eval\n"
                                 "<!-- promptwise:managed:end -->")
    assert score_skill(patched).score > base


# ── optimizer end-to-end ─────────────────────────────────────────────────────
def _seed_store(tmp_path):
    db = tmp_path / "learning.db"
    s = LearningStore(db)
    s.capture("security", "used eval on untrusted input", "use ast.literal_eval", project="demo")
    s.capture("style", "demo pack functions too long", "split into helpers", project="demo")
    return db


def test_optimize_accepts_and_writes(tmp_path):
    db = _seed_store(tmp_path)
    skill = tmp_path / "SKILL.md"
    skill.write_text(SKILL, encoding="utf-8")
    out = optimize_skill_pack(skill, project="demo", db_path=db)
    assert out["accepted"] and out["written"]
    assert out["score_after"] > out["score_before"]
    txt = skill.read_text(encoding="utf-8")
    assert "promptwise:managed:start" in txt
    assert "ast.literal_eval" in txt
    # frontmatter preserved at top
    assert txt.startswith("---\nname: demo-pack")
    ok, _ = validate_skill(txt)
    assert ok


def test_optimize_dry_run_does_not_write(tmp_path):
    db = _seed_store(tmp_path)
    skill = tmp_path / "SKILL.md"
    skill.write_text(SKILL, encoding="utf-8")
    out = optimize_skill_pack(skill, project="demo", db_path=db, dry_run=True)
    assert out["accepted"] and not out["written"]
    assert "promptwise:managed:start" not in skill.read_text(encoding="utf-8")


def test_optimize_is_reversible_and_idempotent(tmp_path):
    db = _seed_store(tmp_path)
    skill = tmp_path / "SKILL.md"
    skill.write_text(SKILL, encoding="utf-8")
    optimize_skill_pack(skill, project="demo", db_path=db)
    once = skill.read_text(encoding="utf-8")
    # re-running replaces the managed region in place — no duplicate blocks
    optimize_skill_pack(skill, project="demo", db_path=db)
    twice = skill.read_text(encoding="utf-8")
    assert twice.count("promptwise:managed:start") == 1
    # deleting the managed region restores the original prose
    import re
    restored = re.sub(r"\n*<!-- promptwise:managed:start.*?promptwise:managed:end -->\n*",
                      "\n", twice, flags=re.DOTALL).rstrip() + "\n"
    assert "ast.literal_eval" not in restored


def test_optimize_no_corrections(tmp_path):
    db = tmp_path / "empty.db"
    LearningStore(db)  # create empty store
    skill = tmp_path / "SKILL.md"
    skill.write_text(SKILL, encoding="utf-8")
    out = optimize_skill_pack(skill, project="demo", db_path=db)
    assert not out["accepted"] and "no corrections" in out["reason"]


def test_optimize_missing_file(tmp_path):
    out = optimize_skill_pack(tmp_path / "nope.md")
    assert not out["accepted"] and "not found" in out["reason"]


# ── server dispatch ──────────────────────────────────────────────────────────
def test_server_dispatch_optimize(tmp_path, monkeypatch):
    db = _seed_store(tmp_path)
    skill = tmp_path / "SKILL.md"
    skill.write_text(SKILL, encoding="utf-8")
    # the optimizer resolves LearningStore from its own namespace -> patch there
    import promptwise.core.skill_optimizer as so
    orig = so.LearningStore
    monkeypatch.setattr(so, "LearningStore", lambda p=None: orig(db))
    import promptwise.server as srv
    out = json.loads(asyncio.run(srv.call_tool(
        None, "optimize_skill_pack", {"skill_path": str(skill), "project": "demo", "dry_run": True})))
    assert out["accepted"] and out["score_after"] > out["score_before"]
