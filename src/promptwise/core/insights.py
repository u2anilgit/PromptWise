"""insights — correction trends over the local LearningStore.

Aggregates captured corrections by category, project, and time so a team can see
where the agent keeps slipping. Pure stdlib, offline.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from promptwise.core.learning_store import LearningStore


def compute_insights(db_path: str | Path | None = None) -> dict:
    store = LearningStore(db_path)
    rows = store.all()
    total = len(rows)
    by_category = Counter(r.category or "uncategorized" for r in rows)
    by_project = Counter(r.project or "unknown" for r in rows)

    # crude monthly bucket from ISO timestamps (YYYY-MM)
    by_month: Counter = Counter()
    for r in rows:
        by_month[(r.ts or "")[:7]] += 1

    # most-repeated mistakes (normalised)
    mistake_counts = Counter((r.mistake or "").strip().lower() for r in rows if r.mistake)
    top_mistakes = [{"mistake": m, "count": c} for m, c in mistake_counts.most_common(5)]

    return {
        "total_learnings": total,
        "fts": store.fts_enabled,
        "by_category": dict(by_category.most_common()),
        "by_project": dict(by_project.most_common()),
        "by_month": dict(sorted(by_month.items())),
        "top_mistakes": top_mistakes,
        "top_category": by_category.most_common(1)[0][0] if by_category else None,
    }
