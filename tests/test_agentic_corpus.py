"""WP2 2d -- OWASP Agentic Top 10 attack-family corpus candidates. This
task produces reviewable candidates ONLY -- it does not call
promote_corpus_candidates (which mutates corpus/injection_corpus.json) or
re-bless the red-team baseline. Both require a human's explicit
confirmation as a separate follow-up action, per this project's
caution-not-block review pattern for detection-logic changes.
"""
import asyncio
import json
import typing

from promptwise.core.tool_registry import ServerContext
from promptwise.handlers.security import _handle_review_corpus_candidates
from promptwise.security.scanner import SecurityScanner

CANDIDATES_PATH = "corpus/wp2_agentic_candidates.json"


class _Ctx:
    """Lightweight ServerContext stand-in: this handler only reads
    ctx.security, not the full ServerContext shape (mirrors the pattern
    used in tests/test_security_handlers.py)."""

    def __init__(self):
        self.security = SecurityScanner()


_ACTX = typing.cast(ServerContext, _Ctx())


def test_candidates_file_has_all_four_new_families():
    data = json.loads(open(CANDIDATES_PATH, encoding="utf-8").read())
    families = {c["family"] for c in data["cases"]}
    assert families == {"goal_hijack", "memory_poisoning", "fake_approval_agent", "readme_instruction_injection"}


def test_candidates_file_has_both_attack_and_benign_examples_per_family():
    data = json.loads(open(CANDIDATES_PATH, encoding="utf-8").read())
    by_family = {}
    for c in data["cases"]:
        by_family.setdefault(c["family"], []).append(c["is_attack"])
    for family, flags in by_family.items():
        assert True in flags, f"{family} has no attack example"
        assert False in flags, f"{family} has no benign near-miss example"


def test_candidates_each_have_unique_ids():
    data = json.loads(open(CANDIDATES_PATH, encoding="utf-8").read())
    ids = [c["id"] for c in data["cases"]]
    assert len(ids) == len(set(ids))


def test_review_corpus_candidates_dry_run_scores_them():
    out = json.loads(asyncio.run(_handle_review_corpus_candidates(_ACTX, {"path": CANDIDATES_PATH})))
    assert "summary" in out or "results" in out  # match this tool's actual response shape
    assert "error" not in out
