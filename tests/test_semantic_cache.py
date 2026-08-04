"""Phase 19 / candidate D2.2 -- semantic cache: exact-match-always-wins,
fail-open without the embeddings extra, and similarity-matching logic
exercised deterministically via an injected fake provider.
"""
import pytest

from promptwise.core.semantic_cache import (
    DEFAULT_MIN_SIMILARITY,
    SemanticCache,
    _pack_vector,
    _unpack_vector,
)


class _FakeProvider:
    """Deterministic stand-in for EmbeddingProvider: maps known text
    prefixes to fixed vectors so similarity is fully predictable."""

    def __init__(self, mapping=None, ready=True):
        self.mapping = mapping or {}
        self._ready = ready

    def embed(self, text):
        for prefix, vec in self.mapping.items():
            if prefix != "__default__" and prefix in text:
                return vec
        return self.mapping.get("__default__")

    def status(self):
        return {"ready": self._ready}


@pytest.fixture
def cache(tmp_path):
    provider = _FakeProvider()
    return SemanticCache(tmp_path / "cache.db", provider=provider), provider


# ── vector pack/unpack ──────────────────────────────────────────────────────
def test_pack_unpack_roundtrip():
    vec = [0.1, -0.2, 3.5, 0.0]
    assert _unpack_vector(_pack_vector(vec)) == pytest.approx(vec)


# ── fail-open without embeddings dependency (real, unfaked provider) ───────
def test_get_falls_back_to_exact_only_without_provider(tmp_path):
    sc = SemanticCache(tmp_path / "cache.db")  # real EmbeddingProvider, no extra installed
    put_result = sc.put("some_tool", {"q": "hello"}, {"answer": 42})
    assert put_result.stored is True

    exact_hit = sc.get("some_tool", {"q": "hello"})
    assert exact_hit.hit is True
    assert exact_hit.exact is True
    assert exact_hit.value == {"answer": 42}

    near_miss = sc.get("some_tool", {"q": "totally different query"})
    assert near_miss.hit is False
    assert near_miss.exact is False


def test_put_still_stores_exact_entry_when_embedding_none(tmp_path):
    provider = _FakeProvider(mapping={})  # embed() always returns None (no default)
    sc = SemanticCache(tmp_path / "cache.db", provider=provider)
    result = sc.put("t", {"q": "x"}, {"v": 1})
    assert result.stored is True
    got = sc.get("t", {"q": "x"})
    assert got.hit is True and got.exact is True


# ── exact match always wins ─────────────────────────────────────────────────
def test_exact_match_wins_over_semantic(cache):
    sc, provider = cache
    provider.mapping["__default__"] = [1.0, 0.0]
    sc.put("t", {"q": "hello world"}, {"v": "exact"})

    result = sc.get("t", {"q": "hello world"})
    assert result.hit is True
    assert result.exact is True
    assert result.similarity == 1.0
    assert result.matched_key == result.key


# ── semantic near-miss ──────────────────────────────────────────────────────
def test_semantic_near_miss_above_threshold(cache):
    sc, provider = cache
    provider.mapping["stored:"] = [1.0, 0.0]
    provider.mapping["query:"] = [0.999, 0.0447]  # cosine sim ~0.999, above default 0.95

    sc.put("t", {"q": "stored: original phrasing"}, {"v": "cached-result"})

    result = sc.get("t", {"q": "query: different phrasing"})
    assert result.hit is True
    assert result.exact is False
    assert result.value == {"v": "cached-result"}
    assert result.similarity >= DEFAULT_MIN_SIMILARITY


def test_semantic_miss_below_threshold(cache):
    sc, provider = cache
    provider.mapping["stored:"] = [1.0, 0.0]
    provider.mapping["query:"] = [0.0, 1.0]  # orthogonal -> similarity 0.0

    sc.put("t", {"q": "stored: original"}, {"v": "cached"})
    result = sc.get("t", {"q": "query: unrelated"})
    assert result.hit is False
    assert result.exact is False


def test_semantic_lookup_scoped_to_tool(cache):
    sc, provider = cache
    provider.mapping["__default__"] = [1.0, 0.0]

    sc.put("tool_a", {"q": "hello"}, {"v": "a"})
    result = sc.get("tool_b", {"q": "hello different"})
    assert result.hit is False


def test_min_similarity_override(cache):
    sc, provider = cache
    provider.mapping["stored:"] = [1.0, 0.0]
    provider.mapping["query:"] = [0.8, 0.6]  # cosine sim 0.8

    sc.put("t", {"q": "stored: original"}, {"v": "cached"})

    default_result = sc.get("t", {"q": "query: variant"})
    assert default_result.hit is False  # 0.8 < default 0.95

    loose_result = sc.get("t", {"q": "query: variant"}, min_similarity=0.5)
    assert loose_result.hit is True
    assert loose_result.value == {"v": "cached"}


# ── stale embedding cleanup ─────────────────────────────────────────────────
def test_stale_embedding_row_cleaned_up_on_miss(cache, tmp_path):
    sc, provider = cache
    provider.mapping["__default__"] = [1.0, 0.0]

    sc.put("t", {"q": "hello"}, {"v": 1}, ttl_seconds=1)
    key = sc.exact.get("t", {"q": "hello"}).key

    # simulate the exact entry expiring/being swept while the embedding row remains
    conn = sc._connect()
    try:
        conn.execute("DELETE FROM exact_cache_entries WHERE cache_key = ?", (key,))
        conn.commit()
    finally:
        conn.close()

    before = sc.stats()["semantic_embeddings_stored"]
    assert before == 1

    result = sc.get("t", {"q": "hello but phrased differently"})
    assert result.hit is False

    after = sc.stats()["semantic_embeddings_stored"]
    assert after == 0


# ── stats ────────────────────────────────────────────────────────────────
def test_stats_reports_embedding_count_and_availability(cache):
    sc, provider = cache
    provider.mapping["__default__"] = [1.0, 0.0]
    sc.put("t", {"q": "a"}, {"v": 1})
    sc.put("t", {"q": "b"}, {"v": 2})

    stats = sc.stats()
    assert stats["semantic_embeddings_stored"] == 2
    assert stats["semantic_available"] is True


def test_stats_availability_false_when_provider_not_ready(tmp_path):
    provider = _FakeProvider(ready=False)
    sc = SemanticCache(tmp_path / "cache.db", provider=provider)
    stats = sc.stats()
    assert stats["semantic_available"] is False


# ── never-cache categories still enforced (inherited from ExactCache) ──────
def test_never_cache_category_not_stored(cache):
    sc, provider = cache
    provider.mapping["__default__"] = [1.0, 0.0]
    from promptwise.core.semantic_cache import NEVER_CACHE_CATEGORIES

    category = next(iter(NEVER_CACHE_CATEGORIES))
    result = sc.put("t", {"q": "secret"}, {"v": 1}, category=category)
    assert result.stored is False

    stats = sc.stats()
    assert stats["semantic_embeddings_stored"] == 0
