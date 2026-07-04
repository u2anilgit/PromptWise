# PromptWise — Phase 12 Roadmap

A retrieval-augmented context manager: `rank_context` ranks and prunes
candidates from the existing trace (audit + learnings) and an
optionally-supplied doc onto one token budget.

Standing guardrails: **local-first, air-gap-safe, no new infra, no new deps,
TDD.**

---

## 12.1 — `rank_context`

`docs/ROADMAP.md` named an unscoped feature candidate: make
`semantic_index` + `context_model` + `doc_sharder` a first-class
retrieval-augmented context manager. This phase implements it as a thin
composition layer, not a new ranking engine:

- Audit + learnings candidates come from `semantic_index.search_trace()`
  unchanged — keyword/BM25 by default, optional local embeddings if the
  caller opts in.
- An optionally-supplied doc (`doc_path` or `doc_text`) is sharded fresh
  each call via `doc_sharder.DocSharder` (no persistence added) and scored
  with the same keyword-overlap function `semantic_index` uses internally,
  so all three sources land on one comparable scale.
- Candidates are pruned to a token budget with the same greedy,
  word-count-as-token-proxy convention `core/optimizer.py`'s
  `Optimizer.optimize()` already established — no new tokenizer dependency.

Wired as the `rank_context` MCP tool. `build_context_model` and
`optimize_context` are untouched; this phase composes existing modules
rather than absorbing them.

## Guardrails

- No new ranking algorithm, no new persistence, no new dependency.
- Fail-soft per source: a broken doc or a failed embeddings import drops
  that source's candidates without failing the call.
- TDD throughout, one commit per task.
