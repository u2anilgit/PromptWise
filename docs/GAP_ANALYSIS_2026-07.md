# PromptWise — Competitive Gap Analysis & Roadmap Candidates (2026-07-08)

Source: three parallel agents — (1) full codebase inventory (12 subsystems, file-level),
(2) market scan against LLM-ops/security/memory tooling (Portkey, Helicone, LiteLLM,
LangSmith, Lakera, Rebuff, Presidio, NeMo Guardrails, mem0, Zep, PromptLayer, Langfuse),
(3) adjacent-plugin scan (caveman, BMAD-METHOD) for directly-portable ideas. Full findings
in session transcript; this doc is the actionable distillation, grouped for phase planning
the way `PHASE6`–`PHASE12_ROADMAP.md` were.

**Not a feature backlog to blindly implement.** Several items below break the standing
guardrail "no new pip dependencies" (semantic cache, vector memory). Each such item is
flagged — it needs an explicit decision to accept a new dependency, not silent inclusion.

---

## Executive summary — top 3 if picking a next phase

1. **Real semantic cache.** `plan_cache` currently only *plans where to place* Anthropic
   prompt-cache breakpoints — no actual cache exists (no store, no TTL, no hit tracking).
   The tool name overclaims relative to the implementation.
2. **Benchmark + upgrade injection/PII detection.** Injection detector is 4 regex phrase
   patterns with a count-based confidence score, unbenchmarked. Public PINT benchmark
   scores competitors at 79–95%; PromptWise's actual score is unknown. PII is regex-only,
   no checksum validation (Luhn), no NER.
3. **VS Code/IDE panel.** None of the 6 major competitors researched (Langfuse, Portkey,
   Helicone, LangSmith, Lakera, PromptLayer) ship an in-editor UI — CLI+web-dashboard is
   universal. This is real, unclaimed differentiation, not parity-chasing.

---

## 1. Caching — hollow claim, biggest gap

**Current:** `core/cache_planner.py:CachePlanner.plan` computes prompt-cache breakpoint
placement and projects savings from `models.yaml` rates. It is a cost *simulator*, not a
cache — nothing is stored or served from PromptWise itself.

**Gaps:**
- No actual result cache (semantic or exact-match) for repeated tool/skill invocations.
- No adaptive similarity threshold — research shows fixed thresholds (GPTCache default
  0.7–0.8) underperform adaptive ones by ~16% precision (MeanCache, arXiv 2403.02694).
- No documented guard against known failure modes: false-positive hits, cross-tenant
  leakage, staleness on time-sensitive facts, never-cache categories (medical/legal/
  financial personalized responses).

**Dependency flag:** a real semantic cache needs either an embedding call (network, opts
out of air-gap-by-default) or a local embedding model (new dependency). Exact-match caching
(hash-based, no embeddings) is deployable within current guardrails and should ship first;
semantic (embedding) caching is a separate, explicitly-scoped follow-up.

## 2. Memory management

**Current:** `learning_store.py` — SQLite + FTS5/BM25, keyword search, local-first, no
vector index by default. Solid, air-gapped, but flat: corrections append, they don't
supersede stale facts.

**Gaps:**
- No fact lifecycle (mem0-style ADD/UPDATE/DELETE/NOOP) — a corrected fact and its
  stale predecessor both remain retrievable.
- No paraphrase/synonym retrieval (needs embeddings — same dependency flag as caching).
- No bi-temporal versioning (Zep/Graphiti: valid-time vs system-time) — larger lift,
  backlog-only, not a near-term candidate.

**Recommendation:** add contradiction/supersession logic to `learning_store.py` first
(no new dependency — pure logic change). Hybrid BM25+vector (merged via Reciprocal Rank
Fusion) is the second step, gated on the same embedding-dependency decision as caching —
worth bundling into one "opt-in local embeddings" phase rather than two.

## 3. Security — real but shallow, unbenchmarked

**Current:** `security/scanner.py` — 100% regex/heuristic. Injection detection: 4 phrase
patterns, confidence = `min(1.0, matches*0.25)`. OWASP scan: 5 of 10 categories (SQLi,
secrets, XSS, command injection, SSL verification). PII: regex only, no checksum
validation, no NER. SBOM: `requirements.txt`/`package.json` only, no lockfile/transitive
resolution.

**Gaps, ranked:**
- **Unbenchmarked injection detector.** Run PromptWise's scanner against the public PINT
  dataset (github.com/lakeraai/pint-benchmark) to get an actual number before claiming
  coverage. Competitors: Lakera 95.2%, Bedrock 89.2%, Protect AI 79.1%.
- **Indirect prompt injection** (content injected via tool output/RAG, not direct user
  input) is now >55% of observed real-world attacks per 2026 survey data and evades
  phrase-pattern filters by construction. A canary-token/exfiltration-check pattern
  (Rebuff-style: inject a hidden token, flag if it leaks back into output) is a
  no-new-dependency way to catch this class.
- **OWASP coverage** — expand past the current 5 categories.
- **PII hardening** — add checksum validation (Luhn for card numbers) as a cheap,
  no-dependency precision improvement; NER-based detection (Presidio-style) is a larger,
  dependency-gated follow-up.
- **SBOM** — transitive dependency resolution and lockfile parsing (`poetry.lock`,
  `package-lock.json`) closes a real completeness gap in `get_sbom`.

**Bug (not a gap, fix regardless):** `predict_cost`'s pricing dict is hardcoded and
duplicates `pricing.yaml`/`models.yaml` — will silently drift out of sync. Router.py
already reads from the registry; `predict_cost` should too.

## 4. AI bias / fairness / responsible-AI — mostly a non-gap

Existing `core/responsible_ai.py` (bias/ethics/grounding checks, advisory-only by design)
is already appropriately scoped. Market research confirms AIF360/Fairlearn-style fairness
metrics are a **structural mismatch** for a coding-agent plugin — they require tabular
protected-attribute data and classifier predictions that PromptWise's I/O shape doesn't
produce. No researched competitor does meaningfully better here.

**Only real candidate:** `harm_categories` in `config/responsible_ai.yaml` ships empty by
default — populate it with a starter set (or document why it's intentionally empty) so
the ethics check isn't silently a no-op out of the box.

**Decision: do not chase fairness-metric parity.** Explicitly out of scope.

## 5. Cost / routing / optimization

**Current:** Adaptive Beta-posterior router (`adaptive_router.py`) over real outcome
history — genuinely more sophisticated than most static-tier routers. `BudgetGuardian`
does threshold-based spend tracking + anomaly detection.

**Gaps:**
- No provider-level *hard* budget enforcement at routing time — currently
  report-after-the-fact. LiteLLM's `provider_budget_routing` blocks a provider once its
  daily cap is hit, before the call. This is a routing-logic change, no new dependency.
- No whole-workflow cost attribution — tool/API execution costs alongside LLM tokens
  (LangSmith does this). Would extend `budget.py`'s tracked-cost shape.

## 6. Non-technical / organizational UX

**Current:** Real Flask dashboard (`dashboard/web.py`) — spend trends, governance panel,
governor action log. Already ahead of CLI-only competitors.

**Gaps:**
- No alerting (Slack/email/webhook) on budget or security thresholds. Helicone
  explicitly markets scheduled cost-summary reports at finance teams, not engineers —
  same audience PromptWise's compliance/governance framing already targets.
- No scheduled report export (PDF/email) for compliance officers — Drata/Credo-AI
  pattern: "answer 'are we governing AI responsibly' without touching a CLI."
- **Genuine differentiation opportunity:** no VS Code/IDE panel exists anywhere in the
  researched competitive set. Building one is unclaimed ground, not catch-up.
- No one-line installer for non-technical setup. Current path is `pip install -e .` +
  manual `.mcp.json` edit — a real barrier given "non-technical people" is named in
  PromptWise's own positioning. (Ported from caveman plugin's `install.sh`/`install.ps1`
  pattern — cheap, high-visibility fix.)
- No statusline presence — caveman ships a terminal statusline badge
  (`hooks/caveman-statusline.ps1`). PromptWise has zero at-a-glance surface (e.g.
  "budget: 40% used" / "last scan: 2h ago") outside the dashboard tab. Low-effort,
  high-visibility addition.

## 7. Multi-platform emitters

**Current:** 5 solid emitters (Claude, AGENTS.md/Codex, Cursor, Copilot, Cline, Gemini)
with a genuine managed-block merge protocol that preserves user edits around a
hash-marked region.

**Gaps:**
- Windsurf and JetBrains AI Assistant have no emitter — README's "multi-platform"
  framing currently overstates actual coverage.
- BMAD-derived idea: a **web-agent single-file bundle** — a packaged agent usable
  directly in ChatGPT/Gemini/Claude.ai web chat, no IDE/CLI/MCP host required. Current
  emitters all assume an IDE or CLI host; this is a structurally different distribution
  mode worth scoping separately.

## 8. Extensibility / developer-friendliness

**Current:** Skill packs are drop-in `.md` files with YAML frontmatter — zero code
required, good extensibility story. MCP tools, by contrast, are all hardcoded as 84
`Tool(name=...)` entries in one 1,354-line `server.py` — no plugin SDK for third-party
tool contributions without editing core.

**Gap:** a decorator/manifest-based tool registration pattern (mirroring the skill-pack
drop-in model) would let the tool surface grow the same way the skill surface already
does. Improves both internal maintainability (`server.py` is a known hotspot) and the
"developer-friendly, extensible" pitch.

**BMAD-derived ideas, lower priority:**
- **Expansion packs** — pluggable domain bundles (e.g. a "fintech-compliance pack" as
  one installable unit) instead of manually assembling from 81 individual skill packs.
- **Named team/config presets** — a curated subset of packs + workflow under one name,
  for non-technical users who don't want to browse 81 options.
- **Standalone checklist library** — quality-gate checklists usable outside the full
  agile loop, lowering the barrier to partial adoption.

## 9. Subagent / orchestration scope discipline

**Current:** `orchestrate_tasks`/`agile_plan` dispatch multi-agent work with no enforced
per-agent scope limits.

**Gap (caveman-derived):** caveman's `cavecrew-builder` hard-refuses edits touching 3+
files; `cavecrew-investigator` is read-only by construction; `cavecrew-reviewer` skips
formatting nits by design. PromptWise's orchestration has no equivalent declarative scope
cap — a real gap the market-research agent independently flagged too (no scope discipline
on multi-agent dispatch generally, industry-wide). Add opt-in `max_files`/scope-guard
config per dispatched role.

## 10. Compliance and audit — ahead of the field, one risk to flag

**Current:** SHA-256 hash-chained audit log + HMAC-signed compliance bundle export —
genuine tamper-evidence, ahead of most researched competitors' plain export.

**Risk, not gap:** named framework mapping (HIPAA/FINRA/GDPR in
`config/compliance/*.yaml`) is thin regex-keyword matching, not real control-depth audit.
As adoption grows, label these clearly as "advisory starting points" in docs/UI, not
compliance certification — avoids overclaiming and the legal exposure that comes with it.

## 11. Governor / autonomous actions — no gap found

Reversible, policy-gated, undo-ledger design (`core/governor.py`) is ahead of anything
found in the researched competitive set. No action needed.

## 12. Reversible-by-default file operations

**Gap (caveman-derived):** caveman's `/caveman:compress` overwrites a file but always
keeps a human-readable `FILE.original.md` backup. PromptWise's in-place rewriters
(`compress_prompt`, `deslop`, context-optimization tools) have no equivalent backup
convention. Cheap trust-builder, currently absent — adopt the same pattern anywhere
PromptWise rewrites a file in place.

---

## Proposed phase grouping

Grouped so each phase stays within the existing single-package, TDD, one-clean-commit
convention. Ordering is priority, not a commitment — pick per the usual brainstorm-first
process before opening a `PHASE<N>_ROADMAP.md`.

| Phase candidate | Contents | New dependency? |
|---|---|---|
| A — Security hardening | PINT benchmark run + injection detector upgrade, indirect-injection canary check, OWASP coverage expansion, PII checksum validation, SBOM transitive/lockfile parsing | No |
| B — Cost correctness + enforcement | Fix `predict_cost` pricing-dict drift, provider-level hard budget caps at routing time, workflow-level cost attribution | No |
| C — Exact-match cache | Real hash-based result cache (no embeddings) for repeated tool/skill calls | No |
| D — Local-embeddings decision | Bundles semantic cache + hybrid BM25/vector memory + fact-supersession logic behind one opt-in local-embeddings flag | **Yes — decision point** |
| E — Non-technical surface | Alerting (Slack/email/webhook), scheduled report export, one-line installer, statusline badge | No |
| F — Extensibility | Manifest/decorator-based MCP tool registry, subagent scope-guard config | No |
| G — Multi-platform | Windsurf + JetBrains emitters, web-agent single-file bundle | No |
| H — IDE panel | VS Code extension surfacing budget/security/governance at a glance | Likely yes (extension tooling) |

## Effort + model estimate per phase

Effort = dev-days, solo, TDD, one-clean-commit-per-package (matches Phase 6-12 actuals).
Model = PromptWise's own tier language (haiku/sonnet/opus), matched to risk/reasoning
depth, not just task size.

| Phase | Effort | Model | Why |
|---|---|---|---|
| A — Security hardening | 4-6d | **Opus** | Adversarial reasoning (evasion patterns), correctness-critical, false-neg cost high |
| B — Cost correctness + enforcement | 2-3d | **Sonnet** | Well-scoped, mechanical, no adversarial edge cases |
| C — Exact-match cache | 2d | **Sonnet** | Bounded, deterministic, extends existing `cache_planner` pattern |
| D — Local-embeddings decision | 6-8d | **Opus** | New dependency, architecture decision, cache false-positive risk = correctness-critical |
| E — Non-technical surface | 3-4d | **Sonnet** (installer script pieces OK on Haiku) | Integration/plumbing work, low reasoning depth |
| F — Extensibility | 4-5d | **Opus** | Large core refactor (84-tool registry), regression risk same class as Phase 10's `call_tool` work — needs a bijection test |
| G — Multi-platform | 2d (emitters) + 3d (bundle) | **Sonnet** | Emitters follow existing 5-emitter pattern; bundle is new but self-contained |
| H — IDE panel (VS Code) | 6-8d | **Opus** lead, **Sonnet** for UI boilerplate | New tooling surface, architecture-heavy, biggest differentiation bet |

**Total: ~29-38 dev-days** across all 8 phases if run sequentially, solo.

4 of 8 phases (A, D, F, H) need Opus — common thread is correctness-critical or
irreversible-if-wrong work (security, new-dependency architecture, core refactor, new UI
surface). The rest (B, C, E, G) are mechanical/pattern-following and fit Sonnet, matching
this repo's own governed-agile convention of running the dev role at sonnet tier
(`agile_planner.py`). No phase suits Haiku as lead; only isolated sub-tasks (installer
script, boilerplate emitter stub) are Haiku-safe.

## Parallelization plan

Per this repo's own convention (`docs/ROADMAP.md` process notes): parallel wave of
isolated worktrees where files are disjoint; safety-critical/core work lands alone.
File-level overlap check across phases A-H:

| Phase | Primary files touched |
|---|---|
| A | `security/scanner.py`, `core/sbom.py`, `core/mcp_auditor.py` |
| B | `core/router.py`, `plugins/budget.py` |
| C | new module (extends `core/cache_planner.py`) |
| D | `core/semantic_index.py`, `core/learning_store.py`, cache module from C |
| E | `dashboard/web.py`, `dashboard/cli.py`, `hooks/`, install scripts |
| F | `server.py` (all 84 tool registrations — shared/core file) |
| G | `core/config_emitter.py`, `core/agent_profiles.py` |
| H | new standalone package (VS Code extension), no core Python overlap |

**Wave 1 — parallel (6 phases, disjoint or additive-only overlap):** A, B, C, E, G, H.
Each owns distinct modules; any shared touch to `server.py` (new tool entries) is
additive-only, which this repo's own notes confirm "merge cleanly under git ort."

**Wave 2 — solo, sequenced after wave 1:**
- **D** after C — semantic cache extends C's exact-match cache; also gated on the
  local-embeddings dependency decision, don't bundle into the parallel wave.
- **F** last — refactors tool *registration* itself across the full surface. Running it
  after A/B/C/G land means it refactors against the final tool count once, instead of
  conflicting with each phase's additive `server.py` edits mid-flight (same reasoning
  Phase 10's `call_tool` registry refactor used: behavior-preserving, bijection-tested,
  run alone).

Net: **6 phases in parallel, 2 solo after** — collapses the ~29-38 sequential dev-days to
roughly (slowest wave-1 phase, ~6-8d for A/D-adjacent work) + D (~6-8d) + F (~4-5d) ≈
**16-21 elapsed dev-days** if wave 1 is actually run concurrently across worktrees.

## Explicit non-goals

- AIF360/Fairlearn-style fairness-metric parity — structural mismatch with this
  product's I/O shape, confirmed by market research. Do not build.
- Bi-temporal memory versioning (Zep/Graphiti-style) — real capability gap but large
  lift; not a near-term candidate.

---

Standing guardrails carry over unchanged from `docs/ROADMAP.md`: local-first,
air-gap-safe by default, no branded/competitor model ids, hooks/autonomy fail-open/safe,
TDD, one clean commit per package — **except** where a phase explicitly opts into a new
local dependency (Phase D, H above), which needs its own sign-off before starting.
