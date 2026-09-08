"""model_refresh — opt-in, daily-cached refresh of the model registry.

Keeps ``config/models.yaml`` current without a code change and without breaking
the local-first guarantee:

* **Off by default.** Network access only when ``PROMPTWISE_MODEL_REFRESH`` is
  explicitly enabled. Offline, the registry stays authoritative.
* **At most once a day.** A stamp file (``.promptwise/models_refreshed.json``)
  gates fetches to one per TTL window.
* **Fail-open.** Any error leaves the registry untouched; a session never breaks.
* **History preserved.** Fetched models update status/date/price; models missing
  from the fetch are marked *deprecated*, never deleted — so historical stats and
  point-in-time pricing still resolve.

The provider fetch is injected (``fetch_fn``) so it is fully testable offline; the
default fetch is a no-op because no host call can enumerate a build's models.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from promptwise.asset_paths import resolve_asset

_ENV_FLAG = "PROMPTWISE_MODEL_REFRESH"
_ENV_DAYS = "PROMPTWISE_MODEL_REFRESH_DAYS"
_ENV_JITTER = "PROMPTWISE_MODEL_REFRESH_JITTER"
_STAMP = "models_refreshed.json"

DEFAULT_INTERVAL_DAYS = 5.0
DEFAULT_JITTER_DAYS = 2.0
MIN_INTERVAL_DAYS = 3.0
MAX_INTERVAL_DAYS = 7.0


def enabled() -> bool:
    return os.environ.get(_ENV_FLAG, "").strip().lower() in ("1", "on", "true", "yes")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def refresh_interval_hours(install_key: str | None = None) -> float:
    """The 3-7 day refresh window, jittered per install.

    A fixed TTL makes every install in a fleet refresh on the same day, which
    turns a routine catalog check into a synchronized burst against each
    provider. The offset is derived from a stable hash of the install path, so
    each install sits at a different but reproducible point in the window --
    no coordination, and no random state to persist between runs.

    The result is always clamped into [3, 7] days, so a hostile or mistaken env
    value cannot push an install outside the contract.
    """
    import hashlib

    base = _env_float(_ENV_DAYS, DEFAULT_INTERVAL_DAYS)
    jitter = max(0.0, _env_float(_ENV_JITTER, DEFAULT_JITTER_DAYS))
    if jitter > 0:
        key = install_key if install_key is not None else str(Path.cwd())
        digest = hashlib.sha256(key.encode("utf-8", errors="replace")).digest()
        frac = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF  # 0..1
        base = base + (frac * 2.0 - 1.0) * jitter
    days = min(MAX_INTERVAL_DAYS, max(MIN_INTERVAL_DAYS, base))
    return days * 24.0


def _default_registry_path() -> Path:
    for p in (Path("config") / "models.yaml", resolve_asset("config/models.yaml")):
        if p.exists():
            return p
    return resolve_asset("config/models.yaml")


def _stamp_path(state_dir) -> Path:
    return Path(state_dir) / _STAMP


def _is_fresh(state_dir, ttl_hours: float) -> bool:
    p = _stamp_path(state_dir)
    if not p.exists():
        return False
    try:
        last = json.loads(p.read_text(encoding="utf-8")).get("ts")
        return (datetime.now(timezone.utc) - datetime.fromisoformat(last)) < timedelta(hours=ttl_hours)
    except Exception:
        return False


def _write_stamp(state_dir) -> None:
    try:
        d = Path(state_dir)
        d.mkdir(parents=True, exist_ok=True)
        _stamp_path(state_dir).write_text(
            json.dumps({"ts": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    except Exception:
        pass


def merge(registry_data: dict, fetched: list[dict]) -> dict:
    """Merge a fetched model list into registry data (in place). New models are
    added as-is; existing ones are updated; models missing from the fetch but in
    a fetched family are deprecated (never deleted)."""
    models = registry_data.setdefault("models", [])
    by_alias = {m.get("alias"): m for m in models if m.get("alias")}
    fetched_aliases: set[str] = set()
    fetched_families: set[str] = set()
    for f in fetched:
        alias = f.get("alias")
        if not alias:
            continue
        fetched_aliases.add(alias)
        if f.get("family"):
            fetched_families.add(f["family"])
        if alias in by_alias:
            for k in ("status", "release_date", "price", "family"):
                if k in f:
                    by_alias[alias][k] = f[k]
        else:
            models.append(dict(f))
            by_alias[alias] = models[-1]
    for m in models:
        if m.get("alias") not in fetched_aliases and m.get("family") in fetched_families:
            m["status"] = "deprecated"
    return registry_data


def _default_fetch() -> list[dict]:
    """Every available model source, merged, as registry rows.

    Offline this is just the pinned catalog -- which is the point: the default
    fetch is never empty, so a refresh always has something authoritative to
    reconcile against instead of silently doing nothing.
    """
    try:
        from promptwise.core.model_sources import build_default_registry
        records = build_default_registry().fetch_all()
    except Exception:
        return []
    rows: list[dict] = []
    for rec in records:
        try:
            row = rec.to_registry_row()
            # provider/tier are family-level facts; sync_families lifts them off
            # the row so a source can describe a family it just discovered
            # without a second round-trip.
            if rec.provider:
                row["provider"] = rec.provider
            if rec.tier:
                row["tier"] = rec.tier
            rows.append(row)
        except Exception:
            continue
    return rows


def sync_families(registry_data: dict, rows: list[dict]) -> None:
    """Ensure every family named by a row exists in `families`.

    provider/tier ride in on the row and are lifted onto the family entry, then
    stripped -- matching models.yaml's shape, where those facts live on the
    family and never on the model.
    """
    families = registry_data.setdefault("families", {})
    for row in rows:
        if not isinstance(row, dict):
            continue
        fam = str(row.get("family") or "")
        provider = row.pop("provider", None)
        tier = row.pop("tier", None)
        if not fam:
            continue
        entry = families.get(fam)
        if not isinstance(entry, dict):
            entry = {}
            families[fam] = entry
        if provider and not entry.get("provider"):
            entry["provider"] = provider
        if tier and not entry.get("tier"):
            entry["tier"] = tier


def refresh(*, registry_path=None, state_dir: str | Path = ".promptwise",
            ttl_hours: float | None = None, fetch_fn=None, force: bool = False,
            keep_per_family: int | None = None) -> dict:
    """Refresh the registry if enabled and stale. Returns a small status dict;
    never raises."""
    if not enabled() and not force:
        return {"refreshed": False, "reason": "disabled"}
    if ttl_hours is None:
        ttl_hours = refresh_interval_hours()
    try:
        if not force and _is_fresh(state_dir, ttl_hours):
            return {"refreshed": False, "reason": "fresh"}
        fetched = (fetch_fn or _default_fetch)()
        if not fetched:
            _write_stamp(state_dir)  # honor the TTL even when the fetch is empty
            return {"refreshed": False, "reason": "no data"}
        import yaml
        path = Path(registry_path) if registry_path else _default_registry_path()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        data = data or {}
        data.setdefault("families", {})
        data.setdefault("models", [])
        # Order matters: sync_families strips provider/tier off the rows before
        # merge writes them, and retention runs last so a partial fetch cannot
        # retire the previous generations merge() just deprecated.
        sync_families(data, fetched)
        merge(data, fetched)
        from promptwise.core.model_retention import apply_retention
        apply_retention(data["models"], keep_per_family=keep_per_family)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        _write_stamp(state_dir)
        return {"refreshed": True, "count": len(fetched), "path": str(path)}
    except Exception as e:  # fail-open
        return {"refreshed": False, "error": f"{type(e).__name__}: {e}"}


def maybe_refresh(state_dir: str | Path = ".promptwise") -> dict:
    """Convenience entry for the SessionStart hook: gated, cached, fail-open."""
    return refresh(state_dir=state_dir)
