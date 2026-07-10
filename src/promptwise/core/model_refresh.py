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

_ENV_FLAG = "PROMPTWISE_MODEL_REFRESH"
_STAMP = "models_refreshed.json"


def enabled() -> bool:
    return os.environ.get(_ENV_FLAG, "").strip().lower() in ("1", "on", "true", "yes")


def _default_registry_path() -> Path:
    for p in (Path("config") / "models.yaml",
              Path(__file__).resolve().parents[3] / "config" / "models.yaml"):
        if p.exists():
            return p
    return Path("config") / "models.yaml"


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
    return []  # no host call enumerates a build's models; provider fetch is injected


def refresh(*, registry_path=None, state_dir: str | Path = ".promptwise", ttl_hours: float = 24.0,
            fetch_fn=None, force: bool = False) -> dict:
    """Refresh the registry if enabled and stale. Returns a small status dict;
    never raises."""
    if not enabled() and not force:
        return {"refreshed": False, "reason": "disabled"}
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
        merge(data, fetched)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        _write_stamp(state_dir)
        return {"refreshed": True, "count": len(fetched), "path": str(path)}
    except Exception as e:  # fail-open
        return {"refreshed": False, "error": f"{type(e).__name__}: {e}"}


def maybe_refresh(state_dir: str | Path = ".promptwise") -> dict:
    """Convenience entry for the SessionStart hook: gated, cached, fail-open."""
    return refresh(state_dir=state_dir)
