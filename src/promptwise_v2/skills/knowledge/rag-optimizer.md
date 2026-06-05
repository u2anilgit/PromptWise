---
name: rag-optimizer
description: Analyze and optimize RAG pipeline configuration — chunk size, overlap, retrieval strategy, embedding model, and reranking.
triggers:
  - rag
  - retrieval augmented
  - chunk size
  - embedding
  - vector search
  - retrieval quality
  - context window
depends_on: []
output_schema:
  type: object
  properties:
    current_config:
      type: object
    recommendations:
      type: array
      items:
        type: object
    optimized_config:
      type: object
  required:
    - recommendations
    - optimized_config
roles:
  - Dev
  - IT
model_tier: opus
---

# RAG Optimizer

Analyze a RAG pipeline's configuration and produce actionable, ranked recommendations.

## What to analyze

### Chunking
- **Chunk size**: target 512–1024 tokens. Smaller chunks improve precision; larger chunks preserve context. Recommend based on average document length and query complexity.
- **Overlap**: 10–15% of chunk size reduces boundary artifacts. E.g., 512-token chunks → 51–77 token overlap.
- **Strategy**: fixed-size vs. sentence/paragraph boundary splitting. Boundary splitting is preferred for prose; fixed-size for structured data.

### Retrieval strategy
- **top-k**: simple and fast; suitable when documents are homogeneous.
- **MMR (Maximal Marginal Relevance)**: reduces redundancy; use when top-k returns near-duplicate chunks.
- **Hybrid** (BM25 + vector): best recall for keyword-heavy queries.

### Embedding model
Evaluate trade-off between embedding quality and latency/cost:
- `text-embedding-3-small`: fast, cheap, good for short documents
- `text-embedding-3-large`: higher quality, better for long-form or technical content
- Multilingual models when corpus is multi-language

### Reranking
Apply a cross-encoder reranker as a second stage when top-k > 10. Reranking improves precision at the cost of added latency (~100–300 ms).

## Review internals

Inspect `context_engine.py` for:
- Current chunk_size, overlap, top_k values
- Whether reranking is enabled
- Embedding model in use
- Any hard-coded limits on retrieved tokens

## Recommendation format

Each recommendation object:
```json
{
  "parameter": "chunk_size",
  "current_value": 256,
  "recommended_value": 512,
  "expected_improvement": "+12% recall on long-document queries",
  "rationale": "Current 256-token chunks split mid-sentence on average. Doubling chunk size preserves sentence boundaries and reduces fragmentation."
}
```

## Output

Return:
1. `current_config` — snapshot of detected settings
2. `recommendations` — ordered list (highest impact first)
3. `optimized_config` — a YAML-serializable dict with all recommended values applied, ready to write to config file
