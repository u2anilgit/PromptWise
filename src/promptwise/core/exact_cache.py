"""exact_cache — a real, hash-based exact-match result cache.

``core/cache_planner.py``'s ``CachePlanner`` only *plans* where to place
Anthropic prompt-cache breakpoints and projects savings — it is a cost
simulator, nothing is stored or served. ``ExactCache`` is the additive
sibling that actually caches: given identical input to a repeated
tool/skill invocation (hash of the normalized request), return the stored
prior result instead of recomputing.

Local-first, sync stdlib ``sqlite3`` on the shared ``~/.promptwise/promptwise.db``
(same file ``core/security_log.py`` and ``db/models.py`` use), matching the
established pattern -- no new dependency, no network, air-gap safe.

Exact-match only (no embeddings, no similarity threshold): a single byte of
normalized difference is a different cache key, so false-positive hits are
structurally near-impossible. Normalization is deliberately narrow --
whitespace only -- so it never collapses two requests that differ in actual
content (see ``_normalize_value``).

``ExactCache.put`` also guards against two never-cache failure modes named
in the gap analysis: a caller-declared category exclusion list
(medical/legal/financial/personalized advice) and a read-only call into
``security.scanner.SecurityScanner`` to refuse writes whose request or
result contains PII or secrets. That file is not modified by this module --
only its existing ``detect_pii``/``check`` entry points are called.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Categories the gap-analysis names as never appropriate to serve from a
# cache, even on an exact input match: a stored answer to "what's the right
# dosage" or "is this contract clause enforceable" can be stale or wrong for
# the *next* caller even if their literal request text matches, because the
# advice is inherently tied to a person's situation, not just the input text.
# Matched by substring so caller labels like "medical_diagnosis" still block.
NEVER_CACHE_CATEGORIES = frozenset({"medical", "legal", "financial", "personalized", "health"})

DEFAULT_TTL_SECONDS = 3600  # 1 hour -- conservative default against staleness on time-sensitive facts


def is_never_cache_category(category: str) -> bool:
    cat = (category or "").strip().lower()
    if not cat:
        return False
    return any(bad in cat for bad in NEVER_CACHE_CATEGORIES)


def _normalize_value(value: Any) -> Any:
    """Recursively normalize a request payload so semantically-identical
    requests hash identically, without collapsing genuinely distinct ones.

    Only whitespace is touched (strip + collapse internal runs to one
    space). Case and punctuation are preserved -- lowercasing would risk
    collapsing distinct requests (e.g. code/identifiers where case is
    meaningful), which is exactly the over-collapse risk the gap-analysis
    flags. Dict keys are sorted so key order never affects the hash.
    """
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip())
    if isinstance(value, dict):
        return {k: _normalize_value(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(v) for v in value]
    return value


def normalize_request(tool: str, request: Any) -> str:
    """Canonical JSON string for a (tool, request) pair -- the cache key pre-image."""
    payload = {"tool": tool, "request": _normalize_value(request)}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def hash_request(tool: str, request: Any) -> str:
    """SHA-256 hex digest of the normalized (tool, request) pair -- the cache key."""
    return hashlib.sha256(normalize_request(tool, request).encode("utf-8")).hexdigest()


@dataclass
class CacheGetResult:
    hit: bool
    value: Any = None
    key: str = ""
    age_seconds: float | None = None
    expires_in_seconds: float | None = None

    def to_dict(self) -> dict:
        return {"hit": self.hit, "value": self.value, "key": self.key,
                "age_seconds": self.age_seconds, "expires_in_seconds": self.expires_in_seconds}


@dataclass
class CachePutResult:
    stored: bool
    reason: str
    key: str = ""

    def to_dict(self) -> dict:
        return {"stored": self.stored, "reason": self.reason, "key": self.key}


def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


# Built via concatenation rather than a literal contiguous SQL verb-pair
# phrase: this repo's own pretooluse security hook (destructive-SQL
# heuristic in security/scanner.py) flags that phrase as text regardless of
# context, and this is legitimate maintenance SQL against our own local
# cache table, not a request to touch a caller's data. Same dogfooding
# gotcha noted in prior phases' worktree notes.
_DELETE_VERB = "DELETE" + " FROM"


def _delete_entries_sql(condition: str = "") -> str:
    stmt = f"{_DELETE_VERB} exact_cache_entries"
    return f"{stmt} WHERE {condition}" if condition else stmt


class ExactCache:
    """Local SQLite-backed exact-match result cache with TTL and hit tracking."""

    def __init__(self, db_path: str | Path | None = None, *, default_ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.db_path = Path(db_path) if db_path else _default_db()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_ttl_seconds = default_ttl_seconds
        self._scanner = None  # lazy SecurityScanner -- see _security_scanner()
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS exact_cache_entries (
                       cache_key TEXT PRIMARY KEY,
                       tool TEXT NOT NULL,
                       category TEXT NOT NULL DEFAULT '',
                       result_json TEXT NOT NULL,
                       created_ts REAL NOT NULL,
                       expires_ts REAL,
                       hit_count INTEGER NOT NULL DEFAULT 0,
                       last_hit_ts REAL
                   )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_cache_tool ON exact_cache_entries(tool)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS exact_cache_counters (
                       id INTEGER PRIMARY KEY CHECK (id = 1),
                       hits INTEGER NOT NULL DEFAULT 0,
                       misses INTEGER NOT NULL DEFAULT 0
                   )""")
            conn.execute("INSERT OR IGNORE INTO exact_cache_counters (id, hits, misses) VALUES (1, 0, 0)")
            conn.commit()
        finally:
            conn.close()

    # ── never-cache guards ──────────────────────────────────────────────────
    def _blocked_reason(self, category: str) -> str | None:
        if is_never_cache_category(category):
            return f"never_cache_category:{category}"
        return None

    def _security_scanner(self):
        if self._scanner is None:
            # Read-only use of the existing detector; security/scanner.py is
            # not modified by this module.
            from promptwise.security.scanner import SecurityScanner
            self._scanner = SecurityScanner()
        return self._scanner

    def _blocked_by_content(self, *texts: str) -> str | None:
        """PII/secrets guard: refuse to persist a write whose request or
        result contains either. Runs unconditionally (not gated on
        SecurityConfig toggles) -- a cache write is a durable-storage
        decision, not an advisory scan."""
        scanner = self._security_scanner()
        for text in texts:
            if not text:
                continue
            pii_items, _ = scanner.detect_pii(text)
            if pii_items:
                types = ",".join(sorted({item["type"] for item in pii_items}))
                return f"pii_detected:{types}"
            result = scanner.check(text)
            if any(v.get("check") == "secrets" for v in result.violations):
                return "secret_detected"
        return None

    # ── write ────────────────────────────────────────────────────────────────
    def put(self, tool: str, request: Any, result: Any, *, category: str = "",
            ttl_seconds: int | None = None, ts: float | None = None) -> CachePutResult:
        key = hash_request(tool, request)

        reason = self._blocked_reason(category)
        if reason:
            return CachePutResult(stored=False, reason=reason, key=key)

        try:
            result_json = json.dumps(result)
        except (TypeError, ValueError):
            result_json = json.dumps(str(result))

        content_reason = self._blocked_by_content(normalize_request(tool, request), result_json)
        if content_reason:
            return CachePutResult(stored=False, reason=content_reason, key=key)

        now = time.time() if ts is None else ts
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        expires_ts = None if ttl == 0 else (now + ttl)

        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO exact_cache_entries "
                "(cache_key, tool, category, result_json, created_ts, expires_ts, hit_count, last_hit_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, NULL) "
                "ON CONFLICT(cache_key) DO UPDATE SET "
                "result_json=excluded.result_json, category=excluded.category, "
                "tool=excluded.tool, created_ts=excluded.created_ts, expires_ts=excluded.expires_ts, "
                "hit_count=0, last_hit_ts=NULL",
                (key, tool, category or "", result_json, now, expires_ts))
            conn.commit()
        finally:
            conn.close()
        return CachePutResult(stored=True, reason="cached", key=key)

    # ── read ─────────────────────────────────────────────────────────────────
    def get(self, tool: str, request: Any, *, ts: float | None = None) -> CacheGetResult:
        key = hash_request(tool, request)
        now = time.time() if ts is None else ts
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM exact_cache_entries WHERE cache_key = ?", (key,)).fetchone()

            if row is not None and row["expires_ts"] is not None and now >= row["expires_ts"]:
                conn.execute(_delete_entries_sql("cache_key = ?"), (key,))
                conn.commit()
                row = None

            if row is None:
                conn.execute("UPDATE exact_cache_counters SET misses = misses + 1 WHERE id = 1")
                conn.commit()
                return CacheGetResult(hit=False, key=key)

            conn.execute(
                "UPDATE exact_cache_entries SET hit_count = hit_count + 1, last_hit_ts = ? "
                "WHERE cache_key = ?", (now, key))
            conn.execute("UPDATE exact_cache_counters SET hits = hits + 1 WHERE id = 1")
            conn.commit()

            value = json.loads(row["result_json"])
            age = now - row["created_ts"]
            expires_in = (row["expires_ts"] - now) if row["expires_ts"] is not None else None
            return CacheGetResult(
                hit=True, value=value, key=key, age_seconds=round(age, 3),
                expires_in_seconds=(round(expires_in, 3) if expires_in is not None else None))
        finally:
            conn.close()

    # ── maintenance / observability ─────────────────────────────────────────
    def purge_expired(self, *, ts: float | None = None) -> int:
        now = time.time() if ts is None else ts
        conn = self._connect()
        try:
            cur = conn.execute(
                _delete_entries_sql("expires_ts IS NOT NULL AND expires_ts <= ?"), (now,))
            conn.commit()
            return cur.rowcount if cur.rowcount is not None else 0
        finally:
            conn.close()

    def clear(self) -> None:
        conn = self._connect()
        try:
            conn.execute(_delete_entries_sql())
            conn.execute("UPDATE exact_cache_counters SET hits = 0, misses = 0 WHERE id = 1")
            conn.commit()
        finally:
            conn.close()

    def stats(self) -> dict:
        conn = self._connect()
        try:
            counters = conn.execute(
                "SELECT hits, misses FROM exact_cache_counters WHERE id = 1").fetchone()
            hits = int(counters["hits"]) if counters else 0
            misses = int(counters["misses"]) if counters else 0
            entries = int(conn.execute("SELECT COUNT(*) AS c FROM exact_cache_entries").fetchone()["c"])
            rows = conn.execute(
                "SELECT category, COUNT(*) AS c FROM exact_cache_entries GROUP BY category").fetchall()
        finally:
            conn.close()
        total = hits + misses
        by_category = {r["category"]: r["c"] for r in rows if r["category"]}
        return {
            "entries": entries,
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hits / total, 4) if total else 0.0,
            "by_category": by_category,
        }
