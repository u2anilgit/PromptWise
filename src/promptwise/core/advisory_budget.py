"""advisory_budget -- cap what the hooks say, and stop them repeating themselves.

userpromptsubmit_policy runs on every prompt, and preflight plus the skill-match
step can produce eight notes at once. The same "large prompt" or "model routing"
advisory then repeats turn after turn, costing tokens every turn to restate
something the user already read and chose not to act on.

Security notes are exempt from both the dedupe and the byte cap. A budget that
can silently swallow "a credential was pasted into this prompt" is worse than
having no budget at all.
"""
from __future__ import annotations

import os

DEFAULT_MAX_BYTES = 400
_ENV_MAX_BYTES = "PROMPTWISE_ADVISORY_MAX_BYTES"

# A note containing any of these is never deduped and never trimmed away.
_ALWAYS_KEEP = ("secret", "credential", "injection", "blocked", "policy violation", "pii")

_SEEN: dict[str, set[str]] = {}


def max_bytes() -> int:
    raw = os.environ.get(_ENV_MAX_BYTES, "").strip()
    try:
        return max(0, int(raw)) if raw else DEFAULT_MAX_BYTES
    except ValueError:
        return DEFAULT_MAX_BYTES


def reset_session(session_id: str = "") -> None:
    _SEEN.pop(session_id or "", None)


def reset_all() -> None:
    _SEEN.clear()


def _is_critical(note: str) -> bool:
    low = note.lower()
    return any(k in low for k in _ALWAYS_KEEP)


def budget_notes(notes, session_id: str = "", max_bytes_override: int | None = None) -> list[str]:
    """Dedupe within a session, then trim to a byte budget. Never raises.

    Order is preserved. Critical notes are emitted first and unconditionally, so
    a flood of ordinary advisories can never push a security warning out.
    """
    try:
        cleaned = [str(n) for n in (notes or []) if str(n).strip()]
    except Exception:
        return []
    if not cleaned:
        return []

    limit = max_bytes() if max_bytes_override is None else max(0, int(max_bytes_override))
    seen = _SEEN.setdefault(session_id or "", set())

    critical = [n for n in cleaned if _is_critical(n)]
    ordinary = [n for n in cleaned if not _is_critical(n)]

    fresh = []
    for n in ordinary:
        if n in seen:
            continue
        seen.add(n)
        fresh.append(n)

    out: list[str] = list(critical)
    used = sum(len(n) for n in out)
    for n in fresh:
        if used + len(n) > limit:
            continue
        out.append(n)
        used += len(n)
    return out
