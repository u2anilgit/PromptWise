"""effort_router -- reasoning-effort level (low/medium/high), independent of
model tier. Mirrors router.py's _static_tier: same input signals (intent,
stakes), a second, independent decision table. A high-stakes extract still
deserves careful reasoning even though it routes to a cheap model tier, so
effort and tier are computed separately rather than derived from one another.
"""
from __future__ import annotations

EFFORT_ORDER: tuple[str, ...] = ("low", "medium", "high")


def static_effort(intent: str, stakes: str) -> str:
    """The always-available default effort pick."""
    if stakes == "high":
        return "high"
    if stakes == "low" and intent in ("extract", "classify", "summarize", "question"):
        return "low"
    return "medium"
