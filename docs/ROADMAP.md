# PromptWise — Master Roadmap & Progress

Single index over the phased roadmaps. Each phase has its own detailed doc
(`docs/PHASE<N>_ROADMAP.md`). This file is the resume point: what is done, what is
open, and where to pick up next.

**Status as of the last session:** Phases 6–17 complete and merged to `main`
(PRs #5–#12; 13–17 merged locally, not yet PR'd). Working tree clean. **599 tests
pass.** No planned finale — the series is open-ended and continues when new work is
scoped. Remaining feature candidates: D (local-embeddings, needs dependency sign-off)
and H (VS Code panel, likely needs dependency sign-off) — see "Open items" below.

Standing guardrails (all phases): local-first, air-gap-safe, no new infrastructure, no
new pip dependencies, no branded/competitor model ids (tiers/families only), hooks &
autonomy fail-open/safe, additive where possible, one clean commit per package, TDD.

---

## Completed phases

### Phase 6 — governance surface (merged, PRs #5/#6)
Dynamic model+pricing resolver, command/agent surface + `doctor`, dashboard + retention,
safe-parallelization planner (`task_graph`), scaffolding, wave-plan orchestration, opt-in
online model refresh, local-model runtime (device probe + Ollama passthrough + registry
auto-population via a gitignored overlay). Detail: `PHASE6_ROADMAP.md`.

### Phase 7 — intelligence + trust (merged, PR #7) — 285 → 338 tests
- 7.1 adaptive routing that learns from outcome history (`adaptive_router.py`).
- 7.2 signed compliance evidence export from the audit chain (`compliance_export.py`).
- 7.3 eval + regression harness (`eval_harness.py`) — feeds 7.1's outcome store.
- 7.4 cross-host portability check + host-neutral CI emitter (`portability_check.py`).
Detail: `PHASE7_ROADMAP.md`.

### Phase 8 — close the loop + insights (merged, PR #8) — 338 → 352 tests
- 8.1 live-route outcome writer (`route_recorder.py`): real routes + quality verdicts →
  the 7.1 outcome store, so routing learns from production, not just evals.
- 8.2 insights engine (`insights.py`): ranked recommendations (routing/cost/quality/
  budget) + `insights_report` tool + `/insights` + dashboard panel.
Detail: `PHASE8_ROADMAP.md`.

### Phase 9 — autonomous governance (merged, PR #9) — 352 → 374 tests
- Loop verification captured as `tests/test_loop_integration.py`.
- Governor (`governor.py`): insights recs → typed, policy-gated, reversible actions;
  modes `advise` (default) / `dry_run` / `apply` via `PROMPTWISE_AUTONOMY`; allowlist is
  the only path to state change; undo ledger; every event on the hash-chained audit log;
  destructive changes advisory-only forever; fail-safe (no partial state).
Detail: `PHASE9_ROADMAP.md`.

### Phase 10 — debt paydown + loop close (merged, PR #10) — 374 → 390 tests
- 10.1 `call_tool` refactored into a `_HANDLERS` registry (behavior-preserving; 82
  handlers verbatim; bijection test). Clears the complexity debt flagged in Phases 7–9.
- 10.2 `BudgetGuardian` reads the governor's `budget.local.yaml` overlay.
- Alignment fix: governor default root → shared home state dir so an applied
  `AdjustBudgetGuard` reaches the guardian (the budget loop is now genuinely closed).
Detail: `PHASE10_ROADMAP.md`.

### Phase 11 — pyright debt + red-team harness (merged, PR #11) — 390 → 428 tests
- 11.1 cleared all 3 pyright nits: `Counter[str]`/float in `insights.py`, `chain_head`
  narrowing in `compliance_export.py`, async-Session annotations in `db/models.py`
  (`async_sessionmaker`).
- 11.2 consolidated the three duplicated security-handler regex copies in `server.py`
  onto `SecurityScanner` (`detect_injection`/`detect_pii`, merged `check_owasp`);
  `run_security_suite` now aggregates all four checks and persists verdicts
  (`core/security_log.SecurityScanStore`); found + fixed an air-gap violation — the
  scanner's OSV.dev supply-chain lookup was an unconditional live network call, now
  gated behind `allow_network` (default `False`).
- 11.3 `core/redteam_harness.py` — the security analogue of `eval_harness.py`: built-in
  offline attack/benign corpus (14 cases), baseline store, regression gate. Wired as
  `run_red_team_harness`.
Detail: `PHASE11_ROADMAP.md`.

### Phase 12 — retrieval-augmented context manager (merged, PR #12) — 428 → 439 tests
- `core/context_ranker.py`: `rank_context` composes `semantic_index.search_trace`
  (audit + learnings) and `doc_sharder.DocSharder` (optional caller-supplied doc) into
  one ranked, budget-pruned candidate list — reuses existing scoring and
  `Optimizer.optimize()`'s word-count-budget convention, no new ranking algorithm, no
  new persistence, no new dependency. Wired as `rank_context` (84th tool).
Detail: `PHASE12_ROADMAP.md`.

### Wave 1 (gap-analysis candidates A, B, C, E, G) — 5 phases run in parallel worktrees,
merged sequentially to main (2026-07-09) — 431 → 599 tests, 84 → 90 MCP tools. Built
from `docs/GAP_ANALYSIS_2026-07.md`'s 8 ranked candidates; D and H excluded from this
wave (both need explicit new-dependency sign-off, not silent inclusion).

### Phase 13 — security hardening (candidate A, merged locally) — 431 → 462 tests
- `security/injection_benchmark.py`: offline benchmark harness (bundled 30-case
  attack+benign corpus) against the real `detect_injection`; measured baseline
  precision 0.80/recall 0.27/F1 0.40. Replaced the 4 flat regexes with a weighted,
  family-grouped pattern set — F1 rose to 1.00 on the bundled corpus. Optional live
  PINT-dataset fetch gated behind `allow_network=False` (matches the Phase 11 OSV
  convention). Wired as `benchmark_injection`.
- Indirect-injection canary (`scanner.py`): `issue_canary`/`embed_canary`/
  `check_canary_leak`, wired into `scan_response` as an optional signal.
- OWASP coverage 5 → 10 categories (added crypto failures, insecure deserialization,
  SSRF, path traversal, debug-mode).
- PII: Luhn checksum validation on credit-card matches before counting/redacting.
- SBOM: `poetry.lock` + `package-lock.json` (v1-v3) transitive parsing, tagged
  direct/transitive, de-duplicated by purl.
Detail: `PHASE13_ROADMAP.md`.

### Phase 14 — cost correctness + enforcement (candidate B, merged locally) — 431 → 452 tests
- Fixed `predict_cost`'s pricing-dict drift bug (`plugins/budget.py`): it hardcoded its
  own price table, independent of `config/models.yaml`, and had already drifted
  (hardcoded haiku was stale vs. the live registry). Now reads pricing through the same
  registry-first chain `core/router.py` uses.
- Provider-level hard budget cap at routing time: `ProviderConfig.daily_cap_usd` +
  `Router.route(provider_spend_usd=...)` forces the `fast` tier once a provider's cap is
  hit, before the call — not just after-the-fact reporting. Fail-open when no cap/spend
  is supplied.
- Workflow-level cost attribution: `BudgetGuardian.check(tool_cost_usd=...)` — tool/API
  costs now count alongside LLM cost toward limit/alert/burn-rate, surfaced via
  `BudgetStatus.cost_breakdown`.
Detail: `PHASE14_ROADMAP.md`.

### Phase 15 — exact-match cache (candidate C, merged locally) — 431 → 464 tests
- `core/exact_cache.py`: real hash-based (SHA-256 over canonical normalized request)
  result cache for repeated tool/skill invocations — additive sibling to
  `core/cache_planner.py`'s breakpoint-planning simulator, which stays untouched. SQLite
  store on the shared local state DB, default 1h TTL (0 = never-expire opt-out), lazy +
  swept expiry, hit/miss counters.
- Never-cache guard: category substring-match (medical/legal/financial/personalized/
  health) plus a read-only call into the `SecurityScanner` detectors for PII and
  credential leaks on both request and result — blocks caching either.
- Wired as `cache_lookup`/`cache_store`/`cache_stats`.
Detail: `PHASE15_ROADMAP.md`.

### Phase 16 — non-technical/org UX (candidate E, merged locally) — 431 → 499 tests
- `core/alerts.py`: opt-in (default off) Slack/email/webhook alerting via stdlib
  `urllib`/`smtplib` only — a pure subscriber over `BudgetStatus`/security-scan results,
  no edits needed to `plugins/budget.py` or `security/scanner.py`.
- `core/report_export.py` + `core/scheduler.py`: scheduled spend/security/governance
  summary export (Markdown or self-contained HTML, no PDF dependency), pull-based
  `run_if_due()` checked from a `SessionStart` hook. Wired as `export_org_report`.
- `install.sh`/`install.ps1`: one-line installer (pip install -e ., then Claude Code
  CLI marketplace/plugin install if present), backed by an idempotent, non-clobbering
  `.mcp.json` merge (`core/installer_support.py`).
- `core/statusline.py`: at-a-glance budget/security statusline, reusing existing budget
  and security-scan state (no new state store). `promptwise statusline` CLI subcommand
  + `hooks/promptwise-statusline.sh`/`.ps1`.
Detail: `PHASE16_ROADMAP.md`.

### Phase 17 — multi-platform emitters (candidate G, merged locally) — 431 → 446 tests
- Windsurf (`.windsurfrules`) and JetBrains AI Assistant
  (`.aiassistant/rules/promptwise.md`) emitters added to `core/config_emitter.py`,
  matching the existing flat-body `cline` pattern (no `AgentProfile` entry needed) —
  picked up automatically by `sync`/`diff`/`check`/`check_portability`.
- `core/web_bundle.py`: web-agent single-file bundle (BMAD-derived) for ChatGPT/Gemini/
  Claude.ai web chat — flattens governance bundle + active skill packs into one
  pasteable file. Deliberately a separate code path from the managed-block IDE
  emitters (no host config file, full-overwrite semantics). Wired as
  `export_web_bundle`.
- README's "multi-platform" claim corrected: 8 IDE/CLI emitters + the web bundle, tool
  count 84 → 90.
Detail: `PHASE17_ROADMAP.md`.

---

## Open items (resume here)

### Debt (cosmetic — pyright only, suite green)
- `Column[str]` vs `str` pyright noise in `db/models.py` (~19 errors) — a declarative
  SQLAlchemy typing limitation, unrelated to the Phase 11 async-Session fix. Flagged
  and deliberately left alone in both Phase 11 and Phase 12.

### Feature candidates
Both candidates named in two revisions ago (continuous red-team harness, context/RAG
intelligence) are done — Phase 11 and Phase 12 respectively.

The 2026-07-08 gap analysis (`docs/GAP_ANALYSIS_2026-07.md`) produced 8 ranked phase
candidates (A–H). **A, B, C, E, G are done** (Phases 13–17 above, merged locally
2026-07-09 as wave 1). Remaining:
- **D — local-embeddings decision** (semantic cache + hybrid BM25/vector memory +
  fact-supersession, 6-8d, Opus) — needs a new pip dependency, **explicit sign-off
  required** before starting, breaks the standing no-new-deps guardrail. Sequenced
  after C (done) since it extends the exact-match cache.
- **F — extensible MCP tool registry** (decorator/manifest pattern replacing the now
  90 hardcoded `Tool()` entries in `server.py`, 4-5d, Opus) — deliberately deferred
  until last so it refactors registration against the final tool count once, instead
  of conflicting with each wave-1 phase's additive `server.py` edits mid-flight (same
  reasoning as Phase 10's `call_tool` registry refactor).
- **H — VS Code/IDE panel** (6-8d, Opus lead) — biggest differentiation bet, likely
  needs a new dependency (extension tooling), same sign-off requirement as D.

See `docs/GAP_ANALYSIS_2026-07.md` for full analysis, and non-goals (fairness-metric
parity, bi-temporal memory). Brainstorm before opening D, F, or H as a
`PHASE<N>_ROADMAP.md`.

Each future phase: brainstorm → its own `PHASE<N>_ROADMAP.md` → implement (parallel wave
of isolated worktrees where files are disjoint; safety-critical/core work lands alone) →
merge with full suite green after each → PR.

## Process notes worth keeping
- Sibling git worktrees share one editable install (`.pth` → main `src`), so in-worktree
  `pytest` needs `PYTHONPATH=<wt>/src`; the post-merge full suite on the integration
  branch is the true gate. `.git/worktrees` admin dirs stay handle-locked on Windows
  (cosmetic; `git worktree list` stays clean).
- `server.py` is a recurring shared file (tools register there); additive edits merge
  cleanly under git `ort`.
- When two parallel packages share a data file by convention, verify the writer's default
  location equals the reader's at integration — that path/format contract is a real seam.
