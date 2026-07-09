# PromptWise — Phase 15 Roadmap

A real, hash-based exact-match result cache: given identical input to a
tool/skill invocation, return the stored prior result instead of
recomputing. Implements candidate **C** from `docs/GAP_ANALYSIS_2026-07.md`
("Caching — hollow claim, biggest gap"), ranked #1 priority in that
analysis's executive summary.

Standing guardrails: **local-first, air-gap-safe, no new infra, no new
deps, TDD.**

---

## 15.1 — Why this, why now

`core/cache_planner.py:CachePlanner.plan` computes *where* to place
Anthropic prompt-cache breakpoints and projects savings from
`models.yaml` rates — a cost **simulator**. Nothing is stored or served
by PromptWise itself; the tool name (`plan_cache`) overclaims relative to
the implementation. The gap-analysis flags this as the single biggest gap
against LLM-ops caching tooling (GPTCache, Portkey, etc.) and explicitly
scopes exact-match (hash-based, no embeddings) caching as deployable
within current guardrails now, with semantic (embedding) caching as a
separate, dependency-gated follow-up (candidate D — out of scope here).

This phase is **additive**: `CachePlanner` is untouched. A new sibling
module, `core/exact_cache.py`, adds an `ExactCache` class that actually
stores and serves results, following the same local-first SQLite pattern
already established by `learning_store.py` (FTS5 corrections store) and
`core/security_log.py` (scan-result store) — a table on the shared
`~/.promptwise/promptwise.db`, sync `sqlite3`, no new dependency.

## 15.2 — Design

**Cache key.** `hash_request(tool, request)` = SHA-256 of a canonical
JSON encoding of `(tool, normalized_request)`. Normalization is
deliberately conservative — only whitespace is touched (`strip()` +
collapse internal runs to a single space) and dict keys are sorted for
canonical ordering. Case and punctuation are preserved untouched, so two
requests that differ only in incidental whitespace collapse to the same
key (avoids spurious misses), while two requests that differ in actual
content — including case, which matters for code/identifiers — always
hash differently (avoids the false-positive-hit risk the gap-analysis
flags for similarity-threshold caches). Because this is exact-match only,
there is no threshold to tune and no possibility of a near-miss false
positive by construction — the normalization step is the only place
that could over-collapse, and it is scoped to be as narrow as possible.

**Store.** One SQLite table, `exact_cache_entries`, keyed by the cache
key, storing the JSON-encoded result, a caller-supplied `category`
label, creation timestamp, optional expiry timestamp, and a hit counter
(`hit_count`, `last_hit_ts`). A second singleton counters table tracks
cache-wide hits/misses for `stats()` (a miss never produces a row, so it
can't be derived from `entries` alone).

**TTL.** Default 3600s (1 hour) — conservative against the gap-analysis's
"staleness on time-sensitive facts" failure mode. Callers can override
per-call (`ttl_seconds`); `ttl_seconds=0` means "no expiry" (an explicit,
deliberate override for genuinely stable facts, not a default). Expiry is
checked lazily on `get()` — an expired row is deleted and reported as a
miss; `purge_expired()` is available for periodic sweeps (also run by the
`cache_stats` tool by default).

**Hit/miss tracking + stats.** Every `get()` updates either the per-entry
hit counter or the cache-wide miss counter. `stats()` reports entry
count, hits, misses, hit rate, and a per-category breakdown.

**Never-cache guard.** `put()` refuses to store (returns
`stored=False` with a `reason`) when either:

1. **Category exclusion.** The caller-supplied `category` matches (by
   substring) `NEVER_CACHE_CATEGORIES` = `{medical, legal, financial,
   personalized, health}` — the gap-analysis's named failure mode for
   caching personalized advice. This is a declarative hook: callers own
   labeling their own tool/skill's category; the cache only enforces the
   exclusion list.
2. **PII/secrets.** The normalized request and the JSON-encoded result
   are both scanned with the existing `security.scanner.SecurityScanner`
   (`detect_pii` + the `secrets` check inside `check()`) — read-only call
   into that module, no edits to it. Any hit on either check blocks the
   write. This runs unconditionally (not gated on `SecurityConfig`
   toggles) because a cache write is a durable-storage decision, not an
   advisory scan.

Because both guards run inside `put()`, a request that should never be
cached is simply never written — `get()` for it always misses, which is
the fail-safe direction.

## 15.3 — MCP tool surface

Three new tools, following the existing one-tool-per-operation
convention (mirrors `capture_learning`/`replay_learnings`/
`learning_insights` around `learning_store.py`) rather than overloading
`plan_cache`, which stays scoped to breakpoint planning:

- `cache_lookup` — exact-match `get(tool, request)`; returns hit/value/
  age/expiry.
- `cache_store` — exact-match `put(tool, request, result, category,
  ttl_seconds)`; returns whether it was stored and, if not, why (the
  never-cache guard's reason string).
- `cache_stats` — hit/miss/entry-count/hit-rate/per-category report;
  purges expired entries first by default (`purge_expired=true`).

These are primitives a calling agent (or a future tool wrapper) uses
around any repeated tool/skill invocation; this phase does not retrofit
all 84 existing tool handlers to route through the cache automatically —
that would be a much larger, invasive `server.py` change and is out of
scope for a bounded, additive phase (and other phases running in
parallel worktrees also touch `server.py` additively).

## Guardrails

- No new dependency — sync stdlib `sqlite3`, same pattern as
  `learning_store.py` / `core/security_log.py`.
- Exact-match only (no embeddings, no similarity threshold) — false
  positives are structurally near-impossible.
- Fail-safe: guard failures (category or PII/secrets) block the write,
  never the read path.
- Read-only call into `security/scanner.py`; that file is not modified
  (owned by a concurrent sibling phase).
- `CachePlanner` and `plan_cache` are untouched — purely additive.
- TDD throughout; one commit per logical package (store+TTL+hit-tracking
  core, never-cache guard integration, tool wiring).
