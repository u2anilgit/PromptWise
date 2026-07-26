"""Shared keyword/trigger matching helper.

Plain substring containment (``kw in text``) false-positives whenever the
keyword happens to sit inside an unrelated word -- e.g. ``"tag" in "outage"``
or ``"po" in "endpoint"``. Every matcher that scores prompts against a fixed
keyword/trigger list (Router's intent/stakes heuristics, RoleDetector,
SkillLoader's skill_pack triggers) wants "this word/phrase appears as its own
token", not "these bytes appear somewhere in the string" -- so they all route
through this one word-boundary-aware check instead of duplicating (and
independently getting wrong) the same regex.
"""
from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=1024)
def _boundary_pattern(keyword: str) -> re.Pattern:
    # A \w-boundary assertion only makes sense on an edge that's itself a word
    # character -- a keyword like "def " (trailing space) or "tl;dr" already
    # has a non-word edge, where a naive (?!\w)/(?<!\w) would demand the
    # *next* character also be non-word and wrongly reject "def foo():".
    lead = r"(?<!\w)" if keyword[0].isalnum() or keyword[0] == "_" else ""
    trail = r"(?!\w)" if keyword[-1].isalnum() or keyword[-1] == "_" else ""
    return re.compile(lead + re.escape(keyword) + trail, re.IGNORECASE)


def contains_keyword(text: str, keyword: str) -> bool:
    """True iff ``keyword`` (a word or phrase) appears in ``text`` as whole
    word(s), not merely as a substring of some other word."""
    if not keyword:
        return False
    return _boundary_pattern(keyword).search(text) is not None


def any_keyword(text: str, keywords) -> bool:
    return any(contains_keyword(text, kw) for kw in keywords)
