"""semantic_index — search the trace (audit trail + learnings) by meaning.

Indexes two local sources offline:
* the hash-chained audit JSONL written by the Phase 1 hooks, and
* the Phase 2 LearningStore.

Retrieval is keyword/BM25 by default (no infra, no network). If optional local
embeddings are installed (``sentence-transformers``) AND explicitly enabled, it
will use them; otherwise it degrades transparently to the FTS/keyword path. The
return shape is identical either way.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if len(t) > 1]


def _load_audit(audit_path: Path) -> list[dict]:
    out: list[dict] = []
    if not audit_path.exists():
        return out
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        text = " ".join(str(rec.get(k, "")) for k in ("task", "agent", "model", "gate_decision"))
        text += " " + " ".join(rec.get("files_touched", []) or [])
        text += " " + " ".join(rec.get("rules_applied", []) or [])
        out.append({"kind": "audit", "index": rec.get("index"), "text": text.strip(),
                    "ts": rec.get("timestamp", ""), "ref": rec})
    return out


def _score(query_terms: list[str], text: str) -> float:
    if not query_terms:
        return 0.0
    hay = text.lower()
    return float(sum(1 for t in query_terms if t in hay))


def search_trace(query: str, k: int = 5, repo_root: str | Path = ".",
                 audit_path: str | Path | None = None,
                 learning_db: str | Path | None = None,
                 use_embeddings: bool = False) -> dict:
    root = Path(repo_root)
    # default audit location used by the Phase 1 hooks
    apath = Path(audit_path) if audit_path else (root / ".promptwise" / "audit.jsonl")

    docs = _load_audit(apath)

    # learnings via the existing store (its own FTS handles relevance)
    learning_hits = []
    try:
        from promptwise.core.learning_store import LearningStore
        store = LearningStore(learning_db) if learning_db else LearningStore()
        for l in store.search(query, k=k):
            learning_hits.append({"kind": "learning", "score": abs(l.score),
                                  "text": f"{l.category}: {l.mistake} -> {l.correction}",
                                  "ref": l.to_dict()})
    except Exception:
        pass

    backend = "keyword"
    terms = _tokenize(query)
    if use_embeddings:
        try:
            backend = _embed_rank(docs, query)  # mutates docs' score; returns backend label
        except Exception:
            backend = "keyword"  # transparent fallback
    if backend == "keyword":
        for d in docs:
            d["score"] = _score(terms, d["text"])

    audit_hits = sorted([d for d in docs if d.get("score", 0) > 0],
                        key=lambda d: d["score"], reverse=True)[:k]

    combined = audit_hits + learning_hits
    combined.sort(key=lambda d: d.get("score", 0), reverse=True)

    return {
        "query": query,
        "backend": backend,
        "audit_path": str(apath),
        "audit_matches": len(audit_hits),
        "learning_matches": len(learning_hits),
        "results": [{k2: v for k2, v in d.items() if k2 != "ref"} | {"ref": d.get("ref")}
                    for d in combined[:k]],
    }


def _embed_rank(docs: list[dict], query: str) -> str:
    """Best-effort local embedding rank. Raises if unavailable so the caller
    falls back to keyword. No network: uses a locally-installed model only."""
    from sentence_transformers import SentenceTransformer, util  # optional dep
    model = SentenceTransformer("all-MiniLM-L6-v2")
    if not docs:
        return "embeddings"
    q = model.encode(query, convert_to_tensor=True)
    corpus = model.encode([d["text"] for d in docs], convert_to_tensor=True)
    sims = util.cos_sim(q, corpus)[0]
    for d, s in zip(docs, sims):
        d["score"] = float(s)
    return "embeddings"
