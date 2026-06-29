"""learning_replay — surface relevant past corrections before a new task starts.

Top-K retrieval over the local LearningStore (FTS5 BM25, LIKE fallback), returned
both as structured rows and as a compact reminder block ready to inject into a
prompt. Offline, stdlib only.
"""
from __future__ import annotations

from pathlib import Path

from promptwise.core.learning_store import LearningStore


def replay(task_description: str, k: int = 5, project: str | None = None,
           db_path: str | Path | None = None) -> dict:
    store = LearningStore(db_path)
    hits = store.search(task_description, k=k, project=project)
    reminder = _format_reminder(hits)
    return {
        "task": task_description,
        "matched": len(hits),
        "fts": store.fts_enabled,
        "learnings": [l.to_dict() for l in hits],
        "reminder": reminder,
    }


def _format_reminder(hits) -> str:
    if not hits:
        return ""
    lines = ["Relevant past corrections — apply before starting:"]
    for l in hits:
        cat = f"[{l.category}] " if l.category else ""
        proj = f" ({l.project})" if l.project else ""
        lines.append(f"- {cat}{l.mistake} -> {l.correction}{proj}")
    return "\n".join(lines)
