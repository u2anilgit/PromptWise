# PromptWise — Master Roadmap & Progress

Single index over the phased roadmaps. Each phase has its own detailed doc
(`docs/PHASE<N>_ROADMAP.md`). This file is the resume point: what is done, what is
open, and where to pick up next.

**Status as of 2026-07-24:** Phases 6–18 complete and merged to `main`. The
`p0-p1-bugfix-effort-axis` branch (was in-progress as of 2026-07-22) has since
landed, plus a run of further direct-to-main features: handlers/ package split
(90 tools out of `server.py` into 20 category files), governance gap-closure
P0+P1 (9 of 17 items — config-linter hardening, MCP-auditor OWASP mapping,
multi-framework compliance report card, opt-in hard-blocking budget mode,
OTel exporter, AI-BOM fields, policy `extends:` inheritance, SIEM sinks),
within-tier cost-aware routing, dashboard auth/RBAC, executive dashboard,
SOC2/ISO42001/EU-AI-Act compliance mapping, Ed25519 compliance-bundle
signing, residual-risk register, ADR/decision-memory log, real static-analysis
wiring (`validate_output`), and advisory-only cross-provider cost comparison
(`compare_providers`). `main` is at **795 Python tests**, package version
`1.7.0`. No planned finale — the series is open-ended. See "Open items" below
for what's left; only one older feature candidate remains fully parked: **D**
(local-embeddings, needs dependency sign-off) — explicitly deferred/skipped by
the user, pick up only if asked.

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

### Phase F — decorator-based MCP tool registry (candidate F, merged, PR #14) — 599 → 605 tests
- Replaced the hand-synced `_TOOL_DEFS` list / `_HANDLERS` dict pair with a `@tool(...)`
  decorator (`ToolRegistry`) — one source of truth per tool, physically adjacent to its
  handler. Guards duplicate names, non-coroutine handlers, and malformed schemas at
  decoration time instead of only at test time.
- One critical bug found and fixed mid-implementation, structurally uncatchable by the
  test suite: a `__main__`-guard ordering issue in how decorators registered at import
  time vs. server startup. Same class of blind spot documented again in Phase H below —
  worth remembering for any future refactor of import-time registration/decoration.
- Deliberately sequenced last among wave-1-adjacent work so it refactors registration
  against the final tool count once, instead of conflicting with each wave-1 phase's
  additive `server.py` edits mid-flight (same reasoning as Phase 10's `call_tool`
  registry refactor).

### Phase H — VS Code/IDE panel (candidate H, merged, PR #15) — 605 Python + 18 TS tests
- New standalone `vscode-extension/` package (the repo's first non-Python code) — a
  local Budget/Security/Governance dashboard. Spawns `python -m promptwise.server` as a
  child process, talks to it via the official `@modelcontextprotocol/sdk`'s
  `StdioClientTransport` over the same MCP-over-stdio interface Claude Desktop already
  uses — zero backend changes, zero external services, zero daemon.
- New deps are local/no-runtime-network only: `@modelcontextprotocol/sdk`, `typescript`,
  `esbuild`, `@types/vscode`, `@types/node`, `@vscode/vsce` (packaging only). Testing
  uses Node's built-in `node:test`/`node:assert` (Node ≥20 native `.ts` execution) —
  deliberately no `tsx`/`ts-node`/Jest/Mocha, no `@vscode/test-electron`.
- Two real bugs found during review, not by the test suite (same structural-blind-spot
  class as Phase F's bug above): a `postMessage` race before the webview's message
  listener existed (fixed with a `PendingMessageQueue` + ready handshake), and a
  data-leakage-shaped bug where this repo's own dogfooding audit artifacts
  (`.promptwise/audit.jsonl`) leaked into the shipped `.vsix` (fixed via
  `.gitignore`/`.vscodeignore`).
- v1 dashboard scope deliberately limited to zero-required-argument MCP tools (many of
  PromptWise's 90 tools need input text/code and can't be auto-refreshed status tiles).

### Phase 18 — pyright debt clear + audit-chain race fix + VS Code panel bug fixes (direct commits, 2026-07-10) — 605 tests, 0 pyright errors
- Cleared all pyright debt: 115 → 0 errors across 32 files, via 6 parallel per-file-
  cluster agents (no worktree isolation needed — file-disjoint). Root-cause fixes, not
  suppressions: migrated `db/models.py`/`core/task_tracker.py` off classic
  `Column(...)` to SQLAlchemy 2.0 `Mapped[]`/`mapped_column()` (also fixed a real bug —
  a sync `sessionmaker` bound to an `AsyncEngine`, replaced with `async_sessionmaker`);
  `isinstance`-narrowed the Anthropic content-block union in `core/orchestrator.py`;
  fixed a real `float(None)` crash risk in `core/router.py`/`plugins/budget.py` from
  malformed price rows; Windows platform guards for POSIX-only `os`/`asyncio` calls;
  `typing.cast` for test-double `ServerContext` stand-ins.
- Fixed a hash-chain race condition in `AuditLog.append()`: concurrent subagent
  processes (this session's own 6 parallel pyright-fix agents) raced on the same
  `audit.jsonl`, corrupting the chain (duplicate/missing index). Added a stdlib-only
  cross-process file lock with a Windows-specific `PermissionError`-vs-`FileExistsError`
  retry (verified with an 8-process × 15-append stress test).
- Live-verified the VS Code panel for the first time (screen capture + `SendKeys`
  automation, not just backend calls) and found two more real bugs the mocked unit
  tests couldn't catch: `get_roi_report`'s real shape (a pre-aggregated object, not the
  array `buildBudgetTile` assumed) crashed the Budget tab; `style.css` was never
  bundled into `dist/` or linked in the generated HTML, so the panel rendered as
  unstyled plain text. Both fixed; the raw-`JSON.stringify` tile content was also
  replaced with formatted stat tiles (progress bar, badges, placeholders) reusing the
  existing `viewModel.ts` data shapes.

### In progress — governance/FinOps deep-dive: bug fixes + effort-axis routing (branch `p0-p1-bugfix-effort-axis`, pushed 2026-07-22, NOT yet merged) — 623 → 643 tests on the branch
A 5-agent parallel research pass across Coding Intelligence, AI FinOps/ROI, Governance/
Compliance, AI Risk Management, and Model/Effort+Context-optimization produced a spec
(`docs/superpowers/specs/2026-07-21-governance-finops-dashboard-design.md`, gitignored)
and a phased implementation plan
(`docs/superpowers/plans/2026-07-21-governance-finops-p0-p1.md`, gitignored) covering
Phases P0 (bug fixes) and P1 (effort-axis routing + response-size cap); P2 (executive
dashboard) and P3 (competitive-depth features) are separate follow-on plans, not started.

**Done on the branch (9 of 13 tasks, each reviewed clean):**
- `get_budget_status` fixed — was a permanent-zero stub (`_current_spend`/`_daily_burn`
  set once in `__init__`, never written); now reads real month-to-date `cost_logs`.
- Dashboard wiring bug fixed — `cli.py`'s `_start_serve` called
  `create_web_app(cfg)` (wrong param, `memory_manager` never passed), so the web
  dashboard always showed $0/empty regardless of real usage; both the web and CLI
  paths now read real spend via new `_memory_manager`/`_real_budget_status` helpers.
- Deleted `docs/integration/MULTI_PLATFORM.md` — fabricated doc (nonexistent
  `adapters`/`role_detector.RoleDetector`/`auto_role_applier` modules), flagged in the
  2026-07-16 gap-closure plan and never actually removed until now. (5 other docs still
  link to it — pre-existing, out-of-scope debt, not yet cleaned up.)
- Fixed `run_eval`'s misleading description (claimed A/B quality testing; it only
  estimates cost) — caught and fixed a knock-on golden-snapshot-test regression this
  introduced, since the description fix wasn't covered by a full-suite run at the time.
- Deleted dead `core/codex_validator.py` — unwired to any `@tool`, duplicated
  `code_validator.py`'s job with weaker regex checks vs AST.
- New reasoning-**effort** axis (low/medium/high), independent of model tier — a gap
  the research found totally unaddressed: `core/effort_router.py` (static heuristic,
  mirrors `router.py._static_tier`), `core/effort_map.py` + `config/effort_map.yaml`
  (per-provider label→param resolution), `task_graph.py`'s `plan_waves` and
  `agile_planner.AgileStep` both now carry a per-task effort label.

**Still pending (4 of 13 tasks):**
- `core/effort_adapter.py` — the outcome-learning loop over effort (mirrors
  `adaptive_router.py`'s `OutcomeStore`/Bayesian blend), the largest remaining task.
- Wire the effort axis into `route_request`'s response — depends on the adapter above.
- Response-size cap at the `call_tool` choke point (`core/response_budget.py`) — no
  PromptWise tool response was ever size-bounded before.
- Wire `invoke_skill`/`skill_chain` into `cost_logs` + the audit trail — both already
  return real per-call cost/model data that was never persisted.

Resume via `superpowers:subagent-driven-development` against the plan file above,
starting at Task 7; progress ledger at
`.worktrees/p0-p1-bugfix-effort-axis/.superpowers/sdd/progress.md`.

---

## Open items (resume here)

### Next-roadmap backlog (from the 2026-07-23 vision review, 3 of 6 items shipped 2026-07-24)
Effort key: S = <1 day, M = 1-3 days, L = multi-day/needs its own spec.

| Task | Outcome | Effort | Status |
|---|---|---|---|
| Per-project data scoping (`cost_logs` migration) | Makes the dashboard-auth `Identity.projects` field real — schema change + ~30 call sites | L | Not started |
| Deepen `sync_agent_config`/`check_portability`/etc. across Cursor, Copilot, Windsurf | The real "one plugin, every coding agent" seed — biggest differentiator, not yet built out | L | Not started |
| Broader self-learning coverage | `suggest_technique` gains a third outcome-learning axis (categorical, not a ladder — `core/technique_adapter.py`), mirroring the tier/effort pattern | M | **Done** (v1.8.0) |
| Gap-closure P2 (remaining governance items) | Re-scoped 2026-07-24 — see breakdown table below | Split, see below | Re-scoped |
| Session-level cost rollup | `session_cost_report` tool, real per-process `CURRENT_SESSION_ID` replacing hardcoded `"default"` | S-M | **Done** (v1.9.0) |
| Auto skill-match | `userpromptsubmit_policy` hook now surfaces a matching skill on every prompt automatically | S | **Done** (v1.9.0) |
| Device-scoped routing consent | `check_routing_consent`/`grant_routing_consent`, ask-once-per-device bookkeeping | S | **Done** (v1.9.0) |
| ADR/decision-memory log | `record_decision`/`query_decisions`, mirrors the residual-risk register's pattern | S-M | **Done** (v1.5.0) |
| Real static analysis wiring | `validate_output` gains opt-in `use_static_analysis` (ruff/eslint via subprocess, fail-open) | M | **Done** (v1.6.0) |
| Advisory cross-provider routing | `compare_providers` now a real advisory comparison vs. OpenAI/Gemini reference pricing, structurally decoupled from actual routing | M | **Done** (v1.7.0) |

### Gap-closure P2 re-scope (2026-07-24)
Original 8 items from `docs/superpowers/plans/2026-07-16-governance-gap-closure.md`
(gitignored), re-audited against the current codebase — 4 months of subsequent work
(handlers split, gap-closure P0+P1, ADR tool, static analysis, technique
outcome-learning, etc.) had already overtaken parts of this table. Checked each item
by reading the actual current code, not by assuming the original estimate still holds.

| # | Original item | Current status | Verdict |
|---|---|---|---|
| 10 | Reversible compression + cross-agent shared memory dedup | Not started | **Fold into candidate D** (local-embeddings, `docs/GAP_ANALYSIS_2026-07.md`) — same architecture, same new-dependency sign-off blocker. Don't track as a separate P2 item; it's the same decision. |
| 11 | Session-level (multi-call workflow) cost rollup | `task_report` exists but only aggregates *all* tasks globally — no `session_id` grouping, confirmed by reading `TaskTracker.report()`. `cost_logs` already has a `session_id` column (`db/models.py`), so this is additive, not a schema change. | **Still open, ~3h holds up.** Real gap, genuinely S-M. |
| 12 | Prompt version rollback + replay against captured traces | Not started — confirmed no rollback/version-history code in `save_prompt`/`compare_prompts`/prompt registry. | **Still open, ~4h holds up.** |
| 13 | JIT/time-boxed scoped MCP permissions | Not started — `permission_tuner.py` has no expiry/TTL field. | **Still open, ~5h holds up.** |
| 14 | Injection-detection corpus refresh workflow (offline, human-reviewed — not a live ML classifier) | Not started — `injection_benchmark.py` benchmarks against a fixed corpus but has no refresh workflow. | **Still open, ~8h holds up.** |
| 15 | Streaming/partial-output validation with auto-fix | Not started. | **Recommend deprioritize/drop.** Real static-analysis wiring (v1.6.0, `use_static_analysis` on `validate_output`) already covers most of the same ground more simply (real linter output vs. a mid-stream architecture shift); the original plan itself flagged "confirm worth the complexity" before committing effort. |
| 16 | Broaden `sync_agent_config` host coverage: Aider, Goose, OpenHands, Grok CLI | Not started — `config_emitter.py`'s `TARGETS` dict still has the same 8 hosts. | **Fold into the "deepen agent-sync" backlog item above** (Cursor/Copilot/Windsurf) rather than tracking separately — same file, same mechanical pattern, one task not two. |
| 17 | Live in-session command interception, extending PreToolUse hooks | **Largely already done**, just not by this plan — `hooks/pretooluse_bash_guard.py` (denies destructive shell commands), `hooks/pretooluse_secret_scan.py`, and `hooks/tool_call_budget.py` (per-session tool-call ceiling) all exist and fail-open. | **Re-scope to a gap-fill audit, not a 6h build.** Check what the original gap analysis specifically wanted that these three hooks don't already cover before sizing anything. |

**Net result: of the original 8, 2 fold into existing backlog items (10→D, 16→agent-sync
deepening), 1 is already substantially done (17, needs only a small gap-fill audit), 1
should be dropped/deprioritized (15), leaving 3 genuinely independent, still-open items:
#11 (session cost rollup, S-M), #12 (prompt rollback/replay, M), #13 (JIT scoped
permissions, M).** Brainstorm each independently at kickoff — no shared code between
them.

### Feature candidates
The 2026-07-08 gap analysis (`docs/GAP_ANALYSIS_2026-07.md`) produced 8 ranked phase
candidates (A–H). **A, B, C, E, F, G, H are all done** (Phases 13–17 above as wave 1,
plus F and H documented above). Only one remains:
- **D — local-embeddings decision** (semantic cache + hybrid BM25/vector memory +
  fact-supersession, 6-8d, Opus) — needs a new pip dependency, **explicit sign-off
  required** before starting, breaks the standing no-new-deps guardrail. User
  explicitly deferred/skipped this candidate (2026-07-10) — pick up only if asked.

See `docs/GAP_ANALYSIS_2026-07.md` for full analysis, and non-goals (fairness-metric
parity, bi-temporal memory). Brainstorm before opening D as a `PHASE<N>_ROADMAP.md`.

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
