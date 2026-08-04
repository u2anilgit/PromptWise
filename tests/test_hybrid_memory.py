"""Phase 19 / candidate D2.3 -- hybrid memory retrieval: RRF merge of
keyword ranking with local embedding vector similarity, fail-open to
pure keyword ranking whenever embeddings aren't ready.
"""
import pytest

from promptwise.core.hybrid_memory import (
    reciprocal_rank_fusion,
    rerank_facts_hybrid,
)


class _FakeProvider:
    def __init__(self, mapping=None, ready=True):
        self.mapping = mapping or {}
        self._ready = ready

    def embed(self, text):
        for needle, vec in self.mapping.items():
            if needle != "__default__" and needle in text:
                return vec
        return self.mapping.get("__default__")

    def embed_many(self, texts):
        return [self.embed(t) for t in texts]

    def status(self):
        return {"ready": self._ready}


# ── reciprocal_rank_fusion ──────────────────────────────────────────────────
def test_rrf_rewards_items_ranked_high_in_both_lists():
    scores = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "c"]])
    assert scores["a"] > scores["c"]
    assert scores["b"] > scores["c"]


def test_rrf_item_only_in_one_list_still_scored():
    scores = reciprocal_rank_fusion([["a", "b"], ["c"]])
    assert set(scores) == {"a", "b", "c"}


def test_rrf_empty_rankings():
    assert reciprocal_rank_fusion([]) == {}


# ── rerank_facts_hybrid: fail-open cases ────────────────────────────────────
def test_empty_facts_returned_unchanged():
    assert rerank_facts_hybrid("q", []) == []


def test_single_fact_returned_unchanged():
    facts = [{"key": "a", "value": "1", "scope": "org"}]
    assert rerank_facts_hybrid("q", facts) is facts


def test_blank_query_returns_unchanged():
    facts = [{"key": "a", "value": "1", "scope": "org"}, {"key": "b", "value": "2", "scope": "org"}]
    assert rerank_facts_hybrid("   ", facts) is facts


def test_duplicate_ids_returns_unchanged():
    facts = [{"key": "a", "value": "1", "scope": "org"}, {"key": "a", "value": "2", "scope": "org"}]
    assert rerank_facts_hybrid("q", facts) is facts


def test_provider_not_ready_returns_unchanged():
    facts = [{"key": "a", "value": "1", "scope": "org"}, {"key": "b", "value": "2", "scope": "org"}]
    provider = _FakeProvider(mapping={})  # embed() always returns None
    assert rerank_facts_hybrid("q", facts, provider=provider) == facts


def test_partial_embedding_failure_returns_unchanged():
    facts = [{"key": "a", "value": "1", "scope": "org"}, {"key": "b", "value": "2", "scope": "org"}]
    provider = _FakeProvider(mapping={"q": [1.0, 0.0], "a": [1.0, 0.0]})  # 'b' fact fails to embed
    assert rerank_facts_hybrid("q", facts, provider=provider) == facts


def test_real_provider_without_dependency_returns_unchanged(tmp_path):
    # No provider injected -> constructs a real EmbeddingProvider; fastembed
    # genuinely isn't installed in this test env, so this proves the base-
    # install fail-open path end to end.
    facts = [{"key": "a", "value": "1", "scope": "org"}, {"key": "b", "value": "2", "scope": "org"}]
    assert rerank_facts_hybrid("q", facts) == facts


# ── rerank_facts_hybrid: actual reranking via injected provider ────────────
def test_vector_match_promotes_a_keyword_loser():
    # Keyword order (as query_facts would return it): a, b, c -- 'c' ranks
    # last on keywords but is the only semantic match for the query. RRF
    # fuses both signals: c can't out-rank a (which wins on both keyword
    # rank AND ties on the vector list), but it must be promoted past b,
    # which has no signal in either direction.
    facts = [
        {"key": "a", "value": "unrelated", "scope": "org"},
        {"key": "b", "value": "also unrelated", "scope": "org"},
        {"key": "c", "value": "closely matches the query", "scope": "org"},
    ]
    provider = _FakeProvider(mapping={
        "the query": [1.0, 0.0],
        "unrelated": [0.0, 1.0],
        "also unrelated": [0.0, 1.0],
        "closely matches": [0.99, 0.01],
    })
    out = rerank_facts_hybrid("the query", facts, provider=provider)
    assert [f["key"] for f in out] == ["a", "c", "b"]


def test_result_shape_unchanged_by_reranking():
    facts = [
        {"key": "a", "value": "x", "scope": "org"},
        {"key": "b", "value": "y", "scope": "org"},
    ]
    provider = _FakeProvider(mapping={"__default__": [1.0, 0.0]})
    out = rerank_facts_hybrid("q", facts, provider=provider)
    assert sorted(out, key=lambda f: f["key"]) == sorted(facts, key=lambda f: f["key"])
    assert all(set(f) == {"key", "value", "scope"} for f in out)
