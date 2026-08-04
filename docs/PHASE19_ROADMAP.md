# PromptWise — Phase 19 Roadmap (Candidate D: Local Embeddings)

Real semantic cache + hybrid (BM25 + vector) memory retrieval + fact
supersession, gated behind an **opt-in installer extra** — the standing
"no new pip dependencies" guardrail is deliberately broken here, with
explicit sign-off (2026-08-04, following an audience-impact review — see
"Audience decision" below), matching the same category of exception
already granted to the VS Code panel (Phase H).

Standing guardrails that still hold: **local-first, air-gap-safe by
default, no new infra, TDD, fail-open throughout.** The new guardrail this
phase adds: **the base install never changes.** `pip install promptwise`
must produce byte-for-byte the same dependency set after this phase as
before it — everything below is reachable only via an explicit opt-in.

---

## 19.0 — Audience decision (why this is scoped the way it is)

Reviewed against three audience segments before sizing:

- **Solo / indie ("lightweight, on the go")** — current core audience,
  most install-friction-sensitive. Zero impact as long as the base install
  is unchanged, which is the hard requirement this phase is built around.
- **Small-to-mid team** — largely neutral; the real requirement here is
  predictability (whole team opts in together, not silent per-developer
  drift), satisfied by an installer extras group rather than a runtime
  auto-detect.
- **Enterprise / regulated** — net gain: closes a capability gap
  the buyer already compares against mem0/Zep on. The one real risk is
  security review flagging new dependencies in `get_sbom` even when
  unused — mitigated by keeping this a genuinely separate extras group
  (default `get_sbom` output stays unchanged unless the extra is actually
  installed) and by supporting a bring-your-own-model-file path for
  fully egress-locked environments where even a one-time download isn't
  allowed (19.4).

Net: ship it, opt-in, with the packaging discipline in 19.4 as the actual
guardrail that makes "no audience loss" true rather than aspirational.

## 19.1 — Split: D1 (no new dependency) vs D2 (new dependency)

The 2026-07 gap analysis already identified that part of candidate D
needs no new dependency at all. Splitting it out matters because D1 can
ship under the *existing* no-new-deps guardrail — no further sign-off
required — while D2 is the part that actually needs everything below.

**D1 — fact supersession/lifecycle in `learning_store.py`.** Corrections
currently only append; a corrected fact and its stale predecessor both
stay retrievable. Add mem0-style ADD/UPDATE/DELETE/NOOP semantics: a new
correction whose `(category, project)` matches an existing entry closely
enough (exact key match, not similarity — no embeddings yet) marks the
prior one superseded rather than leaving both live. Pure logic change,
same SQLite table, no schema-breaking migration. **S-M effort, no
dependency, could start independent of this plan being finalized.**

**D2 — everything below (19.2–19.6).** Semantic cache, hybrid BM25/vector
memory retrieval, the embedding provider itself. This is the part gated
on the new dependency and sized at 6-8 dev-days / Opus-tier in the
original gap analysis — unchanged assessment, this phase does not shrink
that estimate, it scopes it precisely.

## 19.2 — Embedding provider (D2)

New `src/promptwise/embeddings/provider.py`. Guarded import, exactly like
`core/static_analysis.py`'s fail-open pattern for external linters:

```python
try:
    from fastembed import TextEmbedding
    _EMBEDDINGS_AVAILABLE = True
except ImportError:
    _EMBEDDINGS_AVAILABLE = False
```

Every call site checks `_EMBEDDINGS_AVAILABLE` first and falls back to
the existing exact-match / FTS5-only path when `False` — this is what
lets `src/promptwise/` import cleanly whether or not the extra is
installed, and is why nothing in the base install has to change.

- **Library:** `fastembed` (ONNX Runtime under the hood), not
  `sentence-transformers` — the latter drags in PyTorch (1.5-2GB+),
  incompatible with a "clone it, pip install, go" pitch. Measured install
  footprint of the fastembed path: **~230MB** (onnxruntime, numpy,
  tokenizers, huggingface_hub, fastembed itself).
- **Default model:** `BAAI/bge-small-en-v1.5` (fastembed's own default,
  384-dim, ~65-130MB depending on quantization) — small, well-established,
  no exotic dependency of its own.
- **Lazy singleton.** The model loads on first real embedding call, not
  at import time or server startup — avoids paying RAM/load-time cost for
  installs that have the extra but haven't used it yet in a given
  session.
- **Model source, configurable** (`config/embeddings.yaml`, new file):
  default resolves via fastembed's normal HuggingFace Hub cache path;
  `model_path: <local dir>` overrides to a pre-supplied local model
  directory for fully egress-locked environments (the enterprise
  bring-your-own-model case from 19.0).
- **Network gate.** First-use download only happens when
  `allow_network=True` (same flag name/convention as the existing OSV
  lookup and PINT-benchmark fetch) *and* the model isn't already cached
  locally. `allow_network=False` (the default) with no cached model means
  embedding calls fail open — return "unavailable," callers fall back to
  their existing non-semantic path — never a hard error, never a silent
  network call.

## 19.3 — Consumers (D2)

**Semantic cache** — new `core/semantic_cache.py`, additive sibling to
Phase 15's `core/exact_cache.py` (which stays untouched, same pattern
Phase 15 itself used against `cache_planner.py`). Exact-match lookup
still runs first and still wins on a hit — semantic search is the
fallback for near-misses, not a replacement.

- **Adaptive threshold, not fixed.** The gap analysis cites the
  MeanCache/arXiv 2403.02694 finding that a fixed 0.7-0.8 threshold
  underperforms an adaptive one by ~16% precision. Start conservative
  (~0.95 similarity) with too few calibration samples, loosen only once
  enough hit/miss history exists to justify it — same
  fail-open-to-conservative-default shape as `adaptive_router.py` and
  `effort_adapter.py`'s Beta-posterior blending.
- **Same never-cache guard as Phase 15's `ExactCache.put()`** (category
  exclusion list + PII/secrets scan via `SecurityScanner`) — reused, not
  reimplemented, and if anything more load-bearing here since a fuzzy
  match is a riskier write than an exact one.
- **Storage:** one new SQLite table, embedding stored as a packed
  float32 (or int8-quantized) blob keyed to the existing
  `exact_cache_entries` row. Measured cost: 384 dims × 4 bytes = 1.5KB
  per entry — trivial next to the ~230MB dependency cost; even 50,000
  cached entries is only ~75MB of DB growth.

**Hybrid memory retrieval** — extends `learning_store.py`'s existing
FTS5/BM25 search. Vector similarity results merged via Reciprocal Rank
Fusion (the gap analysis's specific recommendation) rather than a
weighted score blend — RRF needs no score-scale calibration between the
two retrieval methods, which matters since BM25 and cosine-similarity
scores aren't on comparable scales. Falls back to pure FTS5/BM25 (today's
behavior, unchanged) whenever `_EMBEDDINGS_AVAILABLE` is `False`.

## 19.4 — Packaging & installer UX

This is the part that actually enforces "no audience loss" — reviewed
here for sign-off on wording before it's wired into `install.sh`/
`install.ps1`/`pyproject.toml` alongside the D2 implementation (not
before — an installer flag for a feature that doesn't exist yet is
exactly the kind of overclaim `docs/GAP_ANALYSIS_2026-07.md` itself
flagged `plan_cache` for; not repeating that here).

**`pyproject.toml`** — new extras group, isolated from `dev`:
```toml
[project.optional-dependencies]
dev = [...]
embeddings = [
    "fastembed>=0.4,<1.0",
]
```
`pip install promptwise` — unchanged. `pip install "promptwise[embeddings]"`
— opts in.

**`install.sh` / `install.ps1`** — new `--embeddings` flag alongside the
existing `--dev` flag, and a short note printed in **both** paths (so
users who skip it still know the option exists, and users who take it
know exactly what they're agreeing to):

Lightweight path (default, no flag) — appended after the existing
"Verify:" block:
```
PromptWise install: lightweight mode (no embeddings). Local semantic
cache + smarter memory search are available as an optional extra --
re-run with --embeddings to enable. Adds ~300MB, local and offline
after first use. Skipping this changes nothing above.
```

Embeddings path (`--embeddings` passed):
```
PromptWise install: embeddings mode. Installing ~300MB of local ML
dependencies (fastembed/onnxruntime) for semantic cache + memory search.
First real use downloads a small model (~100MB, one time, needs
network) then runs fully offline -- nothing is sent to a third party
at runtime. To go back to lightweight mode: pip uninstall fastembed
onnxruntime.
```

Both messages are deliberately short (matches the installer's existing
terse style), state the size cost up front, and are explicit that
runtime behavior after the one-time download is fully local — the same
claim `SECURITY.md` already makes for the rest of the product, extended
honestly rather than just asserted.

**`README.md` / `INSTALL.md`** — one new row in the existing feature
table, framed as "local, opt-in" rather than folded into the always-on
feature list, so the top-level pitch ("no third-party frameworks, no
network calls for the core features") stays accurate without a caveat
buried in prose.

**`get_sbom`** — no change needed to the tool itself; because the
dependency only exists in the environment when the extra is installed,
a default install's SBOM output is unaffected by construction. Worth a
regression test asserting this explicitly (extras-group deps must not
appear in a base-install SBOM run).

## 19.5 — MCP tool surface (D2)

Prefer extending existing tools over adding new ones, to avoid tool-count
bloat for what is, from a caller's perspective, a quality upgrade to
existing behavior rather than a new capability:

- `cache_lookup` / `cache_store` — unchanged signatures; semantic
  fallback happens automatically inside `cache_lookup` when exact-match
  misses and `_EMBEDDINGS_AVAILABLE` is `True`. No new required params.
- `query_memory` — hybrid retrieval automatically when available, same
  fallback behavior otherwise. No signature change.
- **One new tool:** `embedding_status` — reports extra-installed /
  model-cached / ready state, for `doctor` and troubleshooting. This is
  the one genuinely new capability (introspection), not a rename of
  existing behavior.

## 19.6 — Guardrails

- Base install byte-for-byte unchanged — enforced by a test that asserts
  `pyproject.toml`'s core `dependencies` list is untouched by this phase.
- Fail-open at every layer: import guard, network gate, and (for the
  adaptive threshold) conservative-default-under-thin-history — matches
  the existing router/effort-adapter shape rather than inventing a new
  one.
- Never-cache guard reused verbatim from Phase 15, not reimplemented.
- No existing tool's required-parameter shape changes.
- `CachePlanner`/`plan_cache`, `ExactCache`/`cache_lookup`/`cache_store`,
  and `learning_store.py`'s existing FTS5 path are all additive-only —
  none are modified in a way that changes their behavior when the extra
  isn't installed.
- TDD; one commit per logical package (embedding provider + fail-open
  import guard, semantic cache, hybrid memory retrieval, packaging/
  installer). Semantic cache lands before hybrid memory (mirrors the
  gap analysis's own sequencing: caching was ranked the higher-priority
  gap).

## Effort estimate

| Piece | Effort | Model | Dependency |
|---|---|---|---|
| D1 — fact supersession | S-M (<1-3d) | Sonnet | None — could start now |
| D2.1 — embedding provider + packaging/installer | 1-2d | Sonnet | fastembed |
| D2.2 — semantic cache (adaptive threshold, never-cache guard) | 3-4d | Opus | fastembed |
| D2.3 — hybrid memory (RRF merge, fallback path) | 2-3d | Opus | fastembed |

Total D2: ~6-9 dev-days, consistent with the original gap-analysis
estimate. D1 is separable and doesn't need to block on this plan.

## Non-goals (unchanged from the original gap analysis)

- Bi-temporal memory versioning (Zep/Graphiti-style valid-time vs
  system-time) — real gap, large lift, not in scope here.
- Making embeddings default-on in any install path, ever, without a
  separate, explicit decision to break the "base install unchanged"
  guardrail this phase establishes.
