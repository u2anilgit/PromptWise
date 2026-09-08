"""model_retention -- how many generations of each model family stay routable.

model_refresh.merge() deprecates every model absent from a fetch, which is right
for a full listing and catastrophic for a partial one: a provider endpoint that
returns only its newest model would retire every previous generation in a single
pass. Retention runs after the merge and restores the newest N per family, so the
"at least 2-3 previous models stay resolvable" contract survives a refresh.

Rows are never deleted -- retirement is `status: deprecated`, so historical cost
rows and labels still resolve (same rule as config/models.yaml's own header).
"""
from __future__ import annotations

import os

DEFAULT_KEEP_PER_FAMILY = 3
DEFAULT_MIN_KEEP = 2

_ENV_KEEP = "PROMPTWISE_MODEL_KEEP_PER_FAMILY"


def keep_setting() -> int:
    """Generations to keep per family, from env, floored at DEFAULT_MIN_KEEP."""
    raw = os.environ.get(_ENV_KEEP, "").strip()
    if not raw:
        return DEFAULT_KEEP_PER_FAMILY
    try:
        return max(DEFAULT_MIN_KEEP, int(raw))
    except ValueError:
        return DEFAULT_KEEP_PER_FAMILY


def _sort_key(model: dict) -> tuple[str, str]:
    """Newest first, alias descending as the tiebreak.

    The alias tiebreak is load-bearing, not cosmetic: the shipped catalog omits
    release_date wherever it could not be verified, and versioned aliases
    (grok-4.6 > grok-4.5, gpt-5.6-terra > gpt-5.4) order correctly on the alias
    alone. It also makes the ordering deterministic across runs, which is the
    same rule ModelRegistry.top_n_current applies.
    """
    return (str(model.get("release_date", "")), str(model.get("alias", "")))


def apply_retention(models: list[dict], keep_per_family: int | None = None,
                    min_keep: int = DEFAULT_MIN_KEEP) -> list[dict]:
    """Mark the newest N rows per family `current` and older ones `deprecated`.

    Mutates and returns `models`. Never raises, never removes a row. Rows with no
    family are left untouched -- they belong to no generation sequence, and
    silently retiring one would be worse than keeping it.
    """
    try:
        requested = keep_per_family if keep_per_family is not None else keep_setting()
        keep = max(int(min_keep), int(requested))
    except Exception:
        keep = DEFAULT_KEEP_PER_FAMILY

    by_family: dict[str, list[dict]] = {}
    for m in models:
        if not isinstance(m, dict):
            continue
        fam = str(m.get("family") or "")
        if not fam:
            continue
        by_family.setdefault(fam, []).append(m)

    for rows in by_family.values():
        rows.sort(key=_sort_key, reverse=True)
        for i, m in enumerate(rows):
            m["status"] = "current" if i < keep else "deprecated"
    return models
