# PromptWise — Master Roadmap & Progress

Single index over the phased roadmaps. Each phase has its own detailed doc
(`docs/PHASE<N>_ROADMAP.md`). This file is the resume point: what is done, what is
open, and where to pick up next.

**Status as of the last session:** Phases 6–10 complete and merged to `main`
(PRs #5–#10). Working tree clean. **390 tests pass.** No planned finale — the series is
open-ended and continues when new work is scoped.

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

---

## Open items (resume here)

### Debt (cosmetic — pyright only, suite green)
- `Counter[str]` assigned float impacts in `insights.py`.
- `chain_head` should be `Optional[str]` in `compliance_export.py`.
- async-Session annotations in `db/models.py` (existing `async_sessionmaker` pattern).

### Feature candidates (not yet scoped)
- **Continuous red-team harness** — security analogue of the eval harness: turn the
  one-shot security tools (owasp/injection/secrets) into a continuous adversarial suite
  over prompts + agent configs, with regression gating.
- **Context / RAG intelligence** — make `semantic_index` + `context_model` + `doc_sharder`
  a first-class retrieval-augmented context manager (rank/prune what enters the window).

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
