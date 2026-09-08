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


def _default_runner(cmd: list[str], timeout: float) -> str:
    import subprocess
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    return proc.stdout or ""


def _longest_prefix_meta(alias: str, family_map: dict) -> dict:
    """Longest matching family_map key wins, so 'gizmo-pro' overrides 'gizmo'."""
    best: dict = {}
    best_len = -1
    for prefix, meta in (family_map or {}).items():
        if alias.startswith(prefix) and len(prefix) > best_len and isinstance(meta, dict):
            best, best_len = meta, len(prefix)
    return best


class CliModelSource:
    """Ask an installed agent CLI which models it can reach.

    Many hosts (aider, gemini-cli, codex, ollama) can list their own models
    locally, with no API key and no network egress of our own. That makes a CLI
    probe a better default than an API call for a subscription user, who holds
    no credential and would otherwise sit on a stale catalog forever. Command,
    regex and family mapping all come from config/model_sources.yaml, so adding
    a CLI is a config edit.
    """

    def __init__(self, key, command, pattern, family_map, priority=20,
                 timeout=8.0, runner=None):
        self.key = key
        self.priority = int(priority)
        self._command = list(command or [])
        self._pattern = pattern
        self._family_map = family_map or {}
        self._timeout = float(timeout)
        self._runner = runner or _default_runner

    def available(self) -> bool:
        if not self._command:
            return False
        if self._runner is not _default_runner:
            return True  # injected runner: availability is the caller's business
        import shutil
        return shutil.which(self._command[0]) is not None

    def fetch(self) -> list[ModelRecord]:
        import re
        try:
            stdout = self._runner(self._command, self._timeout)
            rx = re.compile(self._pattern, re.MULTILINE)
        except Exception:
            return []
        out: list[ModelRecord] = []
        seen: set[str] = set()
        try:
            for m in rx.finditer(stdout or ""):
                g = m.groupdict()
                alias = (g.get("alias") or "").strip()
                if not alias or alias in seen:
                    continue
                seen.add(alias)
                d = _longest_prefix_meta(alias, self._family_map)
                out.append(ModelRecord(
                    alias=alias,
                    family=str(g.get("family") or d.get("family") or alias),
                    provider=str(d.get("provider") or ""),
                    tier=str(g.get("tier") or d.get("tier") or ""),
                    release_date=str(g.get("release_date") or ""),
                    context_window=int(d["context_window"]) if d.get("context_window") else None,
                    source=self.key,
                ))
        except Exception:
            return out
        return out


class LocalOverrideSource:
    """The user's own catalog file. Highest priority -- the user always wins.

    Same schema as config/model_catalog.yaml. This is the escape hatch for a
    model PromptWise has never heard of: drop a row in, no code change, no
    network, no waiting for a release.
    """

    key = "local"

    def __init__(self, path=None, priority=40):
        self.priority = int(priority)
        self._path = Path(path) if path is not None else (
            Path.home() / ".promptwise" / "model_catalog.local.yaml")

    def available(self) -> bool:
        try:
            return self._path.is_file()
        except Exception:
            return False

    def fetch(self) -> list[ModelRecord]:
        if not self.available():
            return []
        return [replace(r, source=self.key) for r in load_catalog(self._path)[1]]


def _default_opener(url: str, headers: dict, timeout: float) -> str:
    from urllib.request import Request, urlopen
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - url comes from local config
        return resp.read().decode("utf-8", errors="replace")


def _dig(obj, dotted: str):
    """Walk a dotted path through nested dicts. Returns None on any miss."""
    cur = obj
    for part in str(dotted).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


class ApiModelSource:
    """A provider's own model-listing endpoint, behind two explicit gates.

    Gate 1 is PROMPTWISE_MODEL_REFRESH (the existing global network opt-in --
    see model_refresh.enabled()). Gate 2 is this source's own credential env
    var. Both must be set: enabling network access globally must never cause a
    call to a provider the user has not credentialed.
    """

    def __init__(self, key, url, auth_env, headers=None, list_path="data",
                 field_map=None, family_map=None, priority=30, timeout=10.0, opener=None):
        self.key = key
        self.priority = int(priority)
        self._url = url
        self._auth_env = auth_env
        self._headers = dict(headers or {})
        self._list_path = list_path or "data"
        self._field_map = dict(field_map or {"alias": "id"})
        self._family_map = dict(family_map or {})
        self._timeout = float(timeout)
        self._opener = opener or _default_opener

    def available(self) -> bool:
        import os
        from promptwise.core.model_refresh import enabled as _refresh_enabled
        if not _refresh_enabled():
            return False
        return bool(self._auth_env and os.environ.get(self._auth_env, "").strip())

    def _headers_with_auth(self) -> dict:
        import os
        token = os.environ.get(self._auth_env, "")
        out = {}
        for k, v in self._headers.items():
            out[k] = v.replace("${TOKEN}", token) if isinstance(v, str) else v
        return out

    def fetch(self) -> list[ModelRecord]:
        import json as _json
        try:
            body = self._opener(self._url, self._headers_with_auth(), self._timeout)
            payload = _json.loads(body)
        except Exception:
            return []
        rows = _dig(payload, self._list_path) if self._list_path else payload
        if not isinstance(rows, list):
            return []
        out: list[ModelRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                alias = str(_dig(row, self._field_map.get("alias", "id")) or "").strip()
                if not alias:
                    continue
                d = _longest_prefix_meta(alias, self._family_map)
                rel = self._field_map.get("release_date")
                out.append(ModelRecord(
                    alias=alias,
                    family=str(d.get("family") or alias),
                    provider=str(d.get("provider") or ""),
                    tier=str(d.get("tier") or ""),
                    release_date=str(_dig(row, rel) or "") if rel else "",
                    context_window=int(d["context_window"]) if d.get("context_window") else None,
                    source=self.key,
                ))
            except Exception:
                continue
        return out


def _sources_config_path() -> Path:
    from promptwise.asset_paths import resolve_asset
    local = Path("config") / "model_sources.yaml"
    return local if local.is_file() else resolve_asset("config/model_sources.yaml")


def build_default_registry(config_path=None, *, openers=None, runners=None) -> SourceRegistry:
    """Build the registry declared by config/model_sources.yaml.

    Pinned and local are always registered, config or no config -- they are the
    offline guarantee and the user's escape hatch, and neither should be
    disableable by a malformed config file.
    """
    reg = SourceRegistry()
    reg.register(PinnedCatalogSource())
    reg.register(LocalOverrideSource())
    try:
        p = Path(config_path) if config_path else _sources_config_path()
        if yaml is None or not p.is_file():
            return reg
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        entries = data.get("sources") or []
        if not isinstance(entries, list):
            return reg
    except Exception:
        return reg
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("enabled", True):
            continue
        kind = str(entry.get("kind") or "")
        key = str(entry.get("key") or "")
        if not key:
            continue
        try:
            if kind == "cli":
                reg.register(CliModelSource(
                    key=key, command=entry.get("command") or [],
                    pattern=entry.get("pattern") or r"(?P<alias>\S+)",
                    family_map=entry.get("family_map") or {},
                    priority=entry.get("priority", 20),
                    timeout=entry.get("timeout", 8.0),
                    runner=(runners or {}).get(key)))
            elif kind == "api":
                reg.register(ApiModelSource(
                    key=key, url=entry.get("url") or "",
                    auth_env=entry.get("auth_env") or "",
                    headers=entry.get("headers") or {},
                    list_path=entry.get("list_path") or "data",
                    field_map=entry.get("field_map") or {},
                    family_map=entry.get("family_map") or {},
                    priority=entry.get("priority", 30),
                    timeout=entry.get("timeout", 10.0),
                    opener=(openers or {}).get(key)))
        except Exception:
            continue
    return reg
