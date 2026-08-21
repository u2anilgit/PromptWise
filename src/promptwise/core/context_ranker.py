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

import re
import time
from itertools import combinations
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


_TRUNCATION_MARKERS = ("...", "…", "[truncated]", "[content truncated]")
_NEGATION_MARKERS = ("not ", "never ", "no longer ", "deprecated", "outdated", "obsolete", "removed")


def _structure_score(text: str) -> float:
    """Heuristic 0-1: fraction of non-empty lines that look structured
    (heading, bullet, numbered item, or a short 'label:' line), plus a
    bonus if any heading is present. A cheap line-shape proxy, not a real
    markdown/doc parser -- same spirit as this module's existing
    word-count-as-token-budget proxy in rank_context()."""
    lines = [l for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return 0.0
    structured = sum(
        1 for l in lines
        if l.lstrip().startswith(("#", "-", "*"))
        or re.match(r"^\s*\d+[.)]\s", l)
        or (":" in l[:40] and len(l) < 80)
    )
    score = structured / len(lines)
    if any(l.lstrip().startswith("#") for l in lines):
        score = score + 0.2
    return round(min(1.0, score), 4)


def _is_truncated(text: str) -> bool:
    """Flags a shard as truncated when it ends with a known truncation
    marker, or is long (>200 chars) yet has no terminal punctuation at
    all. Short shards are never penalized for missing punctuation --
    titles/labels/list items legitimately lack it. A heuristic, not a
    real completeness check."""
    stripped = (text or "").rstrip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if any(lowered.endswith(m) for m in _TRUNCATION_MARKERS):
        return True
    if len(stripped) > 200 and stripped[-1] not in ".!?:\"')]":
        return True
    return False


def _staleness_score(source_path: str | None, *, now: float | None = None) -> tuple[float | None, float]:
    """(age_days, freshness_score). age_days is None when source_path is
    absent or unreadable -- 'unknown age' must never be scored as
    'stale', so freshness_score stays 1.0 in that case. Otherwise
    freshness decays linearly from 1.0 (today) to 0.0 (365+ days old)."""
    if not source_path:
        return None, 1.0
    try:
        mtime = Path(source_path).stat().st_mtime
    except OSError:
        return None, 1.0
    age_days = max(0.0, ((now if now is not None else time.time()) - mtime) / 86400.0)
    freshness = max(0.0, 1.0 - min(age_days, 365.0) / 365.0)
    return round(age_days, 2), round(freshness, 4)


def _contradiction_pairs(shards: list[dict], *, overlap_threshold: float) -> dict[str, list[str]]:
    """Pairwise heuristic: two shards are flagged as contradicting when
    they share >= overlap_threshold Jaccard token overlap (same topic)
    AND exactly one of the pair contains a negation/deprecation marker
    the other doesn't. This is a keyword-overlap heuristic, not semantic
    contradiction detection -- documented as such, never claimed more
    precise than it is (ground rule #8)."""
    flags: dict[str, list[str]] = {s["id"]: [] for s in shards}
    for a, b in combinations(shards, 2):
        toks_a, toks_b = set(_tokenize(a["text"])), set(_tokenize(b["text"]))
        union = toks_a | toks_b
        if not union:
            continue
        jaccard = len(toks_a & toks_b) / len(union)
        if jaccard < overlap_threshold:
            continue
        neg_a = any(m in a["text"].lower() for m in _NEGATION_MARKERS)
        neg_b = any(m in b["text"].lower() for m in _NEGATION_MARKERS)
        if neg_a != neg_b:
            flags[a["id"]].append(b["id"])
            flags[b["id"]].append(a["id"])
    return flags


def score_context_quality(
    shards: list[dict], *, contradiction_overlap_threshold: float = 0.5, now: float | None = None,
) -> dict:
    """Structure/completeness/staleness/contradiction quality heuristics
    for a list of already-assembled context shards ({"id", "text",
    optional "source_path"}), extending rank_context's relevance scoring
    with a second, independent quality axis. Advisory only: cheap textual
    heuristics (line-shape, trailing-punctuation, mtime, keyword Jaccard
    overlap), not a real document parser, completeness checker, or
    semantic contradiction detector."""
    ids = [s["id"] for s in shards]
    if len(ids) != len(set(ids)):
        raise ValueError("score_context_quality: shard ids must be unique")

    contradictions = _contradiction_pairs(shards, overlap_threshold=contradiction_overlap_threshold)
    out = []
    for s in shards:
        structure = _structure_score(s["text"])
        truncated = _is_truncated(s["text"])
        completeness = 0.4 if truncated else 1.0
        age_days, freshness = _staleness_score(s.get("source_path"), now=now)
        contradicts = sorted(contradictions.get(s["id"], []))
        penalty = min(0.4, 0.2 * len(contradicts))
        quality_score = round(max(0.0, (structure + completeness + freshness) / 3.0 - penalty), 4)
        out.append({
            "id": s["id"], "structure_score": structure, "completeness_score": completeness,
            "truncated": truncated, "staleness_days": age_days, "freshness_score": freshness,
            "contradicts": contradicts, "quality_score": quality_score,
        })
    return {"shards": out}


LINEAGE_ACTOR = "context_lineage"


def record_context_lineage(
    audit_log, *, retrieval_query: str, shard_ids: list[str], origin_path: str = "", mcp_server: str = "",
) -> dict:
    """Append a context-shard-origin annotation to the audit trail as a
    new record CLASS (actor=LINEAGE_ACTOR) -- never a new table or a
    parallel log. Mirrors security/threat_intel.py::enrich_audit()
    exactly ('the enrichment is a new AuditLog.append() call, same as
    every other append pattern in this codebase'). Surfaces
    automatically in incident_timeline because that tool's
    correlation_key match is a substring search over
    task/rules_applied/compliance_decision -- no incidents.py change
    needed, as long as this appends to the same audit log
    incident_timeline reads (the process-wide _get_audit_log()
    singleton in production; an injected AuditLog in tests)."""
    origin = origin_path or mcp_server or "unknown"
    rules = [f"shard:{sid}" for sid in shard_ids]
    if origin_path:
        rules.append(f"origin_path:{origin_path}")
    if mcp_server:
        rules.append(f"origin_mcp_server:{mcp_server}")
    rec = audit_log.append(
        f"context lineage: retrieved {len(shard_ids)} shard(s) from '{origin}' for query {retrieval_query!r}",
        actor=LINEAGE_ACTOR, agent=mcp_server, rules_applied=rules,
        compliance_decision="context_lineage",
        files_touched=[origin_path] if origin_path else [])
    return {"origin": origin, "shard_ids": list(shard_ids), "record_index": rec.index, "recorded": True}


def list_context_lineage(audit_log, *, contains: str = "", limit: int | None = None) -> list[dict]:
    """Read back lineage records (contains matches the same
    task/rules_applied/compliance_decision substring search
    AuditLog.query() already implements -- no new query surface)."""
    return audit_log.query(actor=LINEAGE_ACTOR, contains=contains or None, limit=limit)
