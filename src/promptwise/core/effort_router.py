"""effort_router -- reasoning-effort level, independent of model tier.

Mirrors router.py's _static_tier: same input signals, a second, independent
decision table. A high-stakes extract still deserves careful reasoning even
though it routes to a cheap model tier, so effort and tier are computed
separately rather than derived from one another.

The ladder spans none..xhigh. The two ends matter: `none` is the difference
between paying for reasoning tokens on a docs lookup and not, and `xhigh` is the
rung a production bugfix deserves. A three-rung ladder made both unreachable.
"""
from __future__ import annotations

EFFORT_ORDER: tuple[str, ...] = ("none", "low", "medium", "high", "xhigh")

# Task types where the answer is mostly retrieval or mechanical transformation --
# reasoning tokens buy nothing. Kept separate from `intent` because preflight
# already computes task_type and the two disagree usefully: a "code" intent on a
# docs task is still a docs task.
_NO_REASONING_TASK_TYPES = frozenset({"docs"})

# Task types where being wrong is expensive to discover later, so the top rung
# is worth its cost.
_DEEP_REASONING_TASK_TYPES = frozenset({"bugfix", "refactor"})

_LOW_EFFORT_INTENTS = frozenset({"extract", "classify", "summarize", "question"})


def static_effort(intent: str, stakes: str, task_type: str = "") -> str:
    """The always-available default effort pick.

    `task_type` is optional and additive: two-argument callers get exactly the
    behavior they had before the ladder was widened.
    """
    intent = (intent or "").lower()
    stakes = (stakes or "").lower()
    task_type = (task_type or "").lower()

    if stakes == "high":
        return "xhigh" if task_type in _DEEP_REASONING_TASK_TYPES else "high"
    if stakes == "low" and intent in _LOW_EFFORT_INTENTS:
        return "none" if task_type in _NO_REASONING_TASK_TYPES else "low"
    return "medium"
