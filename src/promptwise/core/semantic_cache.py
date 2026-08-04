"""semantic_cache — near-miss layer on top of ExactCache (Phase 19 /
candidate D2.2). See docs/PHASE19_ROADMAP.md for the full design.

Additive sibling, same relationship exact_cache.py has to cache_planner.py:
ExactCache itself is never modified (only extended with the additive
get_by_key() helper). SemanticCache wraps it -- every put() first goes
through ExactCache.put() unchanged, inheriting its never-cache guard
(category exclusion + PII/secrets scan) for free rather than
reimplementing it. Exact match always wins on get(): semantic search only
runs on an exact miss, and only when the embeddings extras group is
installed and ready (core/embeddings/provider.py fails open to "not
ready" otherwise) -- degrading silently to exact-match-only behavior is
the same fallback shape as every other opt-in feature in this codebase.

Threshold note (honesty over overclaiming): this is a conservative STATIC
default (0.95), not yet an outcome-learned adaptive one. The gap analysis
recommended starting conservative and only loosening once real hit/miss
feedback justifies it, mirroring adaptive_router.py's Beta-posterior
design -- that calibration loop needs actual labeled feedback (was a
semantic hit's cached result actually still correct?) that doesn't exist
yet, so it's an honest, separately-scoped follow-up, not built here. The
per-call min_similarity override lets a caller tune this today without
waiting on that follow-up.
"""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from promptwise.core.exact_cache import (
    ExactCache,
    NEVER_CACHE_CATEGORIES,  # re-exported for callers that only import this module
    hash_request,
    normalize_request,
)

DEFAULT_MIN_SIMILARITY = 0.95


def _pack_vector(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack_vector(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


@dataclass
class SemanticCacheGetResult:
    hit: bool
    exact: bool  # True = exact-match hit, False = semantic near-miss hit
    value: Any = None
    key: str = ""
    matched_key: str = ""  # the stored entry actually returned (== key when exact)
    similarity: float | None = None
    age_seconds: float | None = None
    expires_in_seconds: float | None = None

    def to_dict(self) -> dict:
        return {
            "hit": self.hit, "exact": self.exact, "value": self.value, "key": self.key,
            "matched_key": self.matched_key, "similarity": self.similarity,
            "age_seconds": self.age_seconds, "expires_in_seconds": self.expires_in_seconds,
        }


def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


class SemanticCache:
    """Wraps ExactCache with an embedding-backed near-miss fallback. Fully
    functional as exact-match-only when the embeddings extra isn't
    installed -- this class never raises because of that, it just never
    finds a semantic candidate."""

    def __init__(self, db_path: str | Path | None = None, *,
                 exact_cache: ExactCache | None = None, provider=None):
        self.db_path = Path(db_path) if db_path else _default_db()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.exact = exact_cache or ExactCache(self.db_path)
        self._provider = provider  # lazy-constructed; injectable for tests
        self._ensure()

    def _connect(self):
        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS semantic_cache_embeddings (
                       cache_key TEXT PRIMARY KEY,
                       tool TEXT NOT NULL,
                       category TEXT NOT NULL DEFAULT '',
                       embedding BLOB NOT NULL,
                       created_ts REAL NOT NULL
                   )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_cache_tool ON semantic_cache_embeddings(tool)")
            conn.commit()
        finally:
            conn.close()

    def _get_provider(self):
        if self._provider is None:
            from promptwise.embeddings.provider import EmbeddingProvider
            self._provider = EmbeddingProvider()
        return self._provider

    # ── write ────────────────────────────────────────────────────────────────
    def put(self, tool: str, request: Any, result: Any, *, category: str = "",
            ttl_seconds: int | None = None, ts: float | None = None):
        """Stores via ExactCache.put() unchanged (same guards, same return
        shape/reason strings). If that succeeds AND an embedding provider
        is available, additionally stores an embedding of the normalized
        request keyed to the same cache_key -- if embedding fails or the
        extra isn't installed, the exact-match entry is still stored; only
        the semantic fallback for it is unavailable."""
        put_result = self.exact.put(tool, request, result, category=category,
                                     ttl_seconds=ttl_seconds, ts=ts)
        if not put_result.stored:
            return put_result

        provider = self._get_provider()
        vec = provider.embed(normalize_request(tool, request))
        if vec is None:
            return put_result  # fail open: exact entry stored, no semantic fallback for it

        now = time.time() if ts is None else ts
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO semantic_cache_embeddings "
                "(cache_key, tool, category, embedding, created_ts) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(cache_key) DO UPDATE SET "
                "embedding=excluded.embedding, category=excluded.category, created_ts=excluded.created_ts",
                (put_result.key, tool, category or "", _pack_vector(vec), now))
            conn.commit()
        finally:
            conn.close()
        return put_result

    # ── read ─────────────────────────────────────────────────────────────────
    def get(self, tool: str, request: Any, *, min_similarity: float = DEFAULT_MIN_SIMILARITY,
            ts: float | None = None) -> SemanticCacheGetResult:
        exact = self.exact.get(tool, request, ts=ts)
        key = hash_request(tool, request)
        if exact.hit:
            return SemanticCacheGetResult(
                hit=True, exact=True, value=exact.value, key=key, matched_key=exact.key,
                similarity=1.0, age_seconds=exact.age_seconds,
                expires_in_seconds=exact.expires_in_seconds)

        provider = self._get_provider()
        query_vec = provider.embed(normalize_request(tool, request))
        if query_vec is None:
            return SemanticCacheGetResult(hit=False, exact=False, key=key)

        from promptwise.embeddings.provider import cosine_similarity

        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT cache_key, embedding FROM semantic_cache_embeddings WHERE tool = ?",
                (tool,)).fetchall()
        finally:
            conn.close()

        best_key, best_sim = None, -1.0
        for row in rows:
            sim = cosine_similarity(query_vec, _unpack_vector(row["embedding"]))
            if sim > best_sim:
                best_key, best_sim = row["cache_key"], sim

        if best_key is None or best_sim < min_similarity:
            return SemanticCacheGetResult(hit=False, exact=False, key=key,
                                          similarity=(best_sim if best_key else None))

        matched = self.exact.get_by_key(best_key, ts=ts)
        if not matched.hit:
            # stale embedding row outlived its exact_cache_entries row (e.g.
            # TTL-expired and swept) -- clean it up and report a miss.
            self._drop_embedding(best_key)
            return SemanticCacheGetResult(hit=False, exact=False, key=key)

        return SemanticCacheGetResult(
            hit=True, exact=False, value=matched.value, key=key, matched_key=best_key,
            similarity=round(best_sim, 4), age_seconds=matched.age_seconds,
            expires_in_seconds=matched.expires_in_seconds)

    def _drop_embedding(self, cache_key: str) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM semantic_cache_embeddings WHERE cache_key = ?", (cache_key,))
            conn.commit()
        finally:
            conn.close()

    def stats(self) -> dict:
        conn = self._connect()
        try:
            embedded = int(conn.execute(
                "SELECT COUNT(*) AS c FROM semantic_cache_embeddings").fetchone()["c"])
        finally:
            conn.close()
        base = self.exact.stats()
        base["semantic_embeddings_stored"] = embedded
        base["semantic_available"] = self._get_provider().status()["ready"]
        return base
