# PromptWise — Master Roadmap & Progress

Single index over the phased roadmaps. Each phase has its own detailed doc
(`docs/PHASE<N>_ROADMAP.md`). This file is the resume point: what is done, what is
open, and where to pick up next.

**Status as of the last session:** Phases 6–12 complete and merged to `main`
(PRs #5–#12). Working tree clean. **439 tests pass.** No planned finale — the series is
open-ended and continues when new work is scoped. No feature candidates currently
queued — see "Open items" below.

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

---

## Open items (resume here)

### Debt (cosmetic — pyright only, suite green)
- `Column[str]` vs `str` pyright noise in `db/models.py` (~19 errors) — a declarative
  SQLAlchemy typing limitation, unrelated to the Phase 11 async-Session fix. Flagged
  and deliberately left alone in both Phase 11 and Phase 12.

### Feature candidates
Both candidates named in the previous revision of this file (continuous red-team
harness, context/RAG intelligence) are done — Phase 11 and Phase 12 respectively.

A competitive gap analysis (2026-07-08, `docs/GAP_ANALYSIS_2026-07.md`) against the
LLM-ops/security/memory tooling market plus adjacent Claude Code plugins (caveman,
BMAD-METHOD) produced 8 ranked phase candidates (A–H): security-detector benchmarking,
cost-tracking correctness + enforcement, exact-match caching, an opt-in local-embeddings
decision (semantic cache + hybrid memory), non-technical/org UX (alerting, scheduled
reports, installer, statusline), an extensible MCP tool registry, additional platform
emitters, and a VS Code panel. See that doc for the full analysis, priority read, and
explicit non-goals (fairness-metric parity, bi-temporal memory). Brainstorm before
opening any of these as a `PHASE<N>_ROADMAP.md` — the table there is priority, not a
commitment.

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
