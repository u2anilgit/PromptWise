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
from pathlib import Path
from typing import Protocol, runtime_checkable

try:
    import yaml
except Exception:  # pragma: no cover - PyYAML is a declared dependency
    yaml = None  # type: ignore


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


def load_catalog(path) -> tuple[dict, list[ModelRecord]]:
    """Parse a catalog file into (families, records). Never raises."""
    try:
        p = Path(path)
        if yaml is None or not p.is_file():
            return {}, []
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return {}, []
        families = data.get("families") or {}
        if not isinstance(families, dict):
            return {}, []
        rows = data.get("models") or []
        if not isinstance(rows, list):
            return families, []
        records: list[ModelRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            alias = str(row.get("alias") or "").strip()
            family = str(row.get("family") or "").strip()
            if not alias or not family:
                continue
            fam = families.get(family) or {}
            fam = fam if isinstance(fam, dict) else {}
            cw = row.get("context_window", fam.get("context_window"))
            records.append(ModelRecord(
                alias=alias,
                family=family,
                provider=str(row.get("provider") or fam.get("provider") or ""),
                tier=str(row.get("tier") or fam.get("tier") or ""),
                status=str(row.get("status") or "current"),
                release_date=str(row.get("release_date") or ""),
                price=row.get("price") if isinstance(row.get("price"), dict) else None,
                context_window=int(cw) if cw else None,
                source="pinned",
            ))
        return families, records
    except Exception:
        return {}, []


class PinnedCatalogSource:
    """The offline guarantee: a catalog shipped with the package.

    Always available, lowest priority -- every other source overrides it. This
    is what makes "no network, no CLIs, no API keys" still produce a complete,
    resolvable catalog, honoring config/models.yaml's local-first contract.
    """

    key = "pinned"
    priority = 10

    def __init__(self, path=None):
        self._path = path

    def _resolve(self) -> Path:
        if self._path is not None:
            return Path(self._path)
        from promptwise.asset_paths import resolve_asset
        local = Path("config") / "model_catalog.yaml"
        return local if local.is_file() else resolve_asset("config/model_catalog.yaml")

    def available(self) -> bool:
        return True

    def fetch(self) -> list[ModelRecord]:
        return load_catalog(self._resolve())[1]
