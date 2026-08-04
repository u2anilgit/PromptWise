"""core.hybrid_memory -- Reciprocal Rank Fusion merge of keyword-ranked
results with local embedding vector similarity (Phase 19 / candidate
D2.3). See docs/PHASE19_ROADMAP.md 19.3.

Additive, fail-open: when the embeddings extra isn't installed (or the
provider isn't ready, or embedding any candidate fails), rerank_facts_hybrid()
returns the input list completely unchanged -- exactly today's
keyword-only ranking, same order, same shape. No new required params on
any caller (query_memory's schema is untouched), no DB schema change:
reranking runs over the already-fetched, already-filtered candidate list
MemoryManager.query_facts() returns, it does not touch or grow the
semantic_facts table.

RRF (not a weighted score blend) because BM25/term-overlap scores and
cosine similarity aren't on comparable scales -- RRF only needs each
list's rank order, not scale-calibrated scores, matching the gap
analysis's specific recommendation.

Cost note: reranking is local ONNX inference over a small, already
DB-filtered candidate list -- it never calls an LLM, never records a
cost_logs row, and never scans the full fact table.
"""
from __future__ import annotations

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = DEFAULT_RRF_K) -> dict[str, float]:
    """rankings: list of ranked-id lists (best first, one entry per list).
    Returns {id: fused_score}, higher is better. Pure stdlib."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _fact_id(fact: dict) -> str:
    return f"{fact.get('scope', '')}::{fact.get('key', '')}"


def rerank_facts_hybrid(query: str, facts: list[dict], *, provider=None) -> list[dict]:
    """facts: MemoryManager.query_facts()'s output, already keyword-ranked
    (term-overlap then recency -- that ranking IS the keyword input list
    for RRF, nothing is recomputed). Reranks via RRF(keyword_rank,
    vector_rank) when the embedding provider is ready; returns facts
    unchanged in every fail-open case below."""
    if not facts or len(facts) < 2 or not (query or "").strip():
        return facts

    ids = [_fact_id(f) for f in facts]
    if len(set(ids)) != len(ids):
        return facts  # duplicate (scope, key) ids -- unsafe to key a rerank by id, skip

    if provider is None:
        from promptwise.embeddings.provider import EmbeddingProvider
        provider = EmbeddingProvider()

    query_vec = provider.embed(query)
    if query_vec is None:
        return facts  # extra not installed / not ready / network-gated -- fail open

    from promptwise.embeddings.provider import cosine_similarity

    fact_texts = [f"{f.get('key', '')} {f.get('value', '')}" for f in facts]
    fact_vecs = provider.embed_many(fact_texts)
    if any(v is None for v in fact_vecs):
        return facts  # partial embedding failure -- don't rerank on incomplete data

    sims = [cosine_similarity(query_vec, v) for v in fact_vecs]
    vector_ranking = [_fact_id(f) for _, f in
                       sorted(zip(sims, facts), key=lambda pair: pair[0], reverse=True)]

    fused = reciprocal_rank_fusion([ids, vector_ranking])
    by_id = {_fact_id(f): f for f in facts}
    ordered_ids = sorted(fused, key=lambda i: fused[i], reverse=True)
    return [by_id[i] for i in ordered_ids if i in by_id]
