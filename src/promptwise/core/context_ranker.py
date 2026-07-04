"""context_ranker — a retrieval-augmented context manager: rank and prune
what enters the window across the trace (audit + learnings, via
``semantic_index.search_trace``) and an optionally-supplied doc (sharded via
``doc_sharder.DocSharder``), onto one token budget.

Design contract:

* **No new ranking algorithm.** Audit/learnings candidates are scored by
  ``semantic_index.search_trace`` exactly as it already does (keyword/BM25 by
  default, optional local embeddings if the caller opts in). Doc shards are
  scored with the same keyword-overlap function so all three sources land on
  one comparable scale.
* **No new persistence.** A doc is supplied per call (``doc_path`` or
  ``doc_text``); shards are computed fresh each time, matching
  ``doc_sharder``'s existing stateless contract.
* **Budget pruning mirrors ``Optimizer.optimize()``.** Word-count-as-token
  proxy, greedy keep-highest-score-first until the budget would be
  exceeded — same shape as the project's existing context-budget tool, no
  new tokenizer dependency.
* **Fail-soft per source.** A broken/missing doc, or an embeddings import
  failure inside ``search_trace``, drops that source's candidates without
  failing the call.
"""
from __future__ import annotations

from pathlib import Path

from promptwise.core.doc_sharder import DocSharder
from promptwise.core.semantic_index import _score, _tokenize, search_trace


def _doc_candidates(query: str, doc_path: str | None, doc_text: str | None) -> list[dict]:
    text = doc_text
    if not text and doc_path:
        try:
            text = Path(doc_path).read_text(encoding="utf-8")
        except Exception:
            return []
    if not text:
        return []
    try:
        shards = DocSharder().shard(text)
    except Exception:
        return []
    terms = _tokenize(query)
    return [{"source": "doc", "id": s.anchor, "text": s.body, "score": _score(terms, s.body)}
            for s in shards]


def _trace_candidates(query: str, sources: tuple[str, ...], *, repo_root: str,
                      audit_path: str | None, learning_db: str | None,
                      use_embeddings: bool) -> list[dict]:
    want_audit = "audit" in sources
    want_learnings = "learnings" in sources
    if not want_audit and not want_learnings:
        return []
    trace = search_trace(query, k=25, repo_root=repo_root, audit_path=audit_path,
                         learning_db=learning_db, use_embeddings=use_embeddings)
    out: list[dict] = []
    for r in trace["results"]:
        kind = r.get("kind")
        if kind == "audit":
            if not want_audit:
                continue
            cid = str(r.get("index", ""))
        elif kind == "learning":
            if not want_learnings:
                continue
            cid = str((r.get("ref") or {}).get("id", ""))
        else:
            continue
        out.append({"source": "learnings" if kind == "learning" else "audit",
                    "id": cid, "text": r.get("text", ""), "score": float(r.get("score", 0.0))})
    return out


def rank_context(query: str, token_budget: int = 2000, *, doc_path: str | None = None,
                 doc_text: str | None = None, sources: tuple[str, ...] = ("audit", "learnings", "doc"),
                 use_embeddings: bool = False, repo_root: str = ".",
                 audit_path: str | None = None, learning_db: str | None = None) -> dict:
    candidates = _trace_candidates(query, sources, repo_root=repo_root, audit_path=audit_path,
                                   learning_db=learning_db, use_embeddings=use_embeddings)
    if "doc" in sources and (doc_path or doc_text):
        candidates.extend(_doc_candidates(query, doc_path, doc_text))

    candidates = [c for c in candidates if c["score"] > 0 and c["text"]]
    candidates.sort(key=lambda c: c["score"], reverse=True)

    budget = max(0, int(token_budget))
    included: list[dict] = []
    used = 0
    dropped = 0
    for c in candidates:
        tokens = len(c["text"].split())
        if used + tokens <= budget:
            included.append(c)
            used += tokens
        else:
            dropped += 1

    return {
        "included": included,
        "dropped_count": dropped,
        "assembled_context": "\n\n".join(c["text"] for c in included),
        "budget": {"total": budget, "used": used},
    }
