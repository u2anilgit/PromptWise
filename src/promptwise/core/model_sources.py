"""model_sources -- pluggable discovery of available models.

A source answers one question: "which models exist right now?". Sources are
independent and unequal -- a pinned offline catalog, a CLI probe, an HTTP API,
and a user's local override file all answer it with different authority. The
registry merges them by alias, higher `priority` winning, and guards each
source separately so one bad source never costs you the others (same
per-step fail-open contract as core/preflight.py).

Adding a provider is a config edit (config/model_sources.yaml), not a code
change: the concrete source classes are generic and configuration-driven.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ModelRecord:
    """One discovered model, in source-neutral form."""
    alias: str
    family: str
    provider: str
    tier: str
    status: str = "current"
    release_date: str = ""
    price: dict | None = None
    context_window: int | None = None
    source: str = ""

    def to_registry_row(self) -> dict:
        """Emit exactly the shape config/models.yaml stores."""
        row: dict = {
            "alias": self.alias,
            "family": self.family,
            "status": self.status,
            "release_date": self.release_date,
        }
        if self.price is not None:
            row["price"] = dict(self.price)
        if self.context_window is not None:
            row["context_window"] = int(self.context_window)
        return row


@runtime_checkable
class ModelSource(Protocol):
    key: str
    priority: int

    def available(self) -> bool: ...

    def fetch(self) -> list[ModelRecord]: ...


class SourceRegistry:
    """Priority-merged fan-in over every registered source."""

    def __init__(self) -> None:
        self._sources: list[ModelSource] = []
        self.errors: list[str] = []

    def register(self, source: ModelSource) -> None:
        self._sources.append(source)

    @property
    def sources(self) -> list[ModelSource]:
        return list(self._sources)

    def fetch_all(self) -> list[ModelRecord]:
        """Every available source's records, merged by alias. Never raises."""
        merged: dict[str, tuple[int, ModelRecord]] = {}
        for src in sorted(self._sources, key=lambda s: getattr(s, "priority", 0)):
            key = getattr(src, "key", src.__class__.__name__)
            try:
                if not src.available():
                    continue
                records = src.fetch() or []
            except Exception as exc:  # fail-open: one source never blocks the rest
                self.errors.append(f"{key}: {type(exc).__name__}: {exc}")
                continue
            prio = int(getattr(src, "priority", 0))
            for rec in records:
                if not getattr(rec, "alias", ""):
                    continue
                stamped = rec if rec.source else replace(rec, source=key)
                prev = merged.get(rec.alias)
                if prev is None or prio >= prev[0]:
                    merged[rec.alias] = (prio, stamped)
        return [rec for _, rec in merged.values()]
