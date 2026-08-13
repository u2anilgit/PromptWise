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
(`compare_providers`). Since then: JIT-scoped MCP permissions, prompt
rollback/replay, injection-corpus refresh, `pretooluse_scan` block→ask fix,
deeper agent-sync (Aider/Goose/OpenHands/Grok emitters + 9-host detection
probes), and (2026-08-03) the combined `core/preflight.py` pass — rewrite
advisory, security scan, task-type classification, model/tier routing, and an
opt-in last-2/3-current-models shortlist, folded into the existing
`userpromptsubmit_policy` hook so every prompt in every host PromptWise emits
hook configs for gets one advisory pass — plus per-project cost scoping
(`cost_logs.project_id`, `project_cost_report`). Package version `1.10.0`. No
planned finale — the series is open-ended. See "Open items" below for what's
left; only one older feature candidate remains fully parked: **D**
(local-embeddings, needs dependency sign-off) — explicitly deferred/skipped by
the user, pick up only if asked. Remote/mobile MCP access is a second
deliberately-parked item: `dashboard/auth.py` states outright that "the MCP
tool layer has no inbound listener and is intentionally out of scope" —
reversing that needs a network-facing-transport/auth/hosting decision, not a
mechanical build, so it's flagged rather than built.

**2026-08-04:** dependency fixes surfaced by a from-scratch install (missing
`sse-starlette` transitive dep, `mcp` version constraint corrected from an
unreleased `>=2.0.0` floor to the installable `>=1.9,<2.0` line, `Tool.inputSchema`
SDK rename in 5 stale tests) — all fixed and verified against the real `mcp`
2.0.0 package (incompatible with `fastapi`'s starlette cap, confirmed by
attempting the upgrade, not assumed). Then a multi-agent-onboarding round:
`promptwise bootstrap --sync-agents` (detects hosts, syncs their native
config in one command instead of requiring a separate `sync_agent_config`
MCP call), a fix so that sync actually populates the skill-pack surface
(family names + drift fingerprint) via the existing `build_surface_bundle()`
helper instead of an empty bundle, Codex MCP server registration in a
repo-scoped `.codex/config.toml` (`sync_codex_mcp()`, deliberately not
routed through the HTML-comment-based managed-block merge since TOML has no
matching comment syntax), and Groq added to the advisory external-pricing
catalog. Antigravity MCP wiring was researched but deliberately held back:
its config lives only at `~/.gemini/config/mcp_config.json` (home-directory
scoped, no project-level override found), a materially bigger blast radius
than every other emitter here (all repo-scoped, git-tracked, reversible) —
needs explicit sign-off before building, same as the still-parked PyPI
publish decision.

**2026-08-13:** WP0 (AI-Generated-Code Trust Gate) shipped — dependency-
hallucination/slopsquatting defense (new `validate_dependencies` tool +
`DependencyGuard`, offline-first typosquat/unlocked-import detection against
`corpus/popular_packages.json` and a project's own lockfiles, optional
`allow_network` PyPI check) plus OWASP scanner hardening (`check_owasp` gains
log-injection and missing-output-encoding/XSS checks). `security_check` now
includes a `dependencies` category by default. No new pip dependencies;
air-gap safe throughout. Full design: `docs/IMPLEMENTATION_PLAN_2026-08.md`
§WP0.

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

### Done — governance/FinOps deep-dive: bug fixes + effort-axis routing (branch `p0-p1-bugfix-effort-axis`, merged to main v1.3.0 — confirmed via `git log`: `3e5b765` wires effort_adapter/effort_map into production; `core/effort_adapter.py` and `core/response_budget.py` both exist on main)
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
  2026-07-16 gap-closure plan and never actually removed until now. Checked 2026-08-01:
  the "5 other docs still link to it" claim was stale — no live markdown link (`[..](..)`)
  to it exists anywhere in the tracked (non-gitignored) tree; the handful of mentions
  left are plain-text filenames in past-tense changelog/roadmap prose (this file,
  `CHANGELOG.md`) plus gitignored `docs/superpowers/` plan scratch files. Nothing to fix.
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

**Remaining 4 of 13 tasks (effort_adapter, route_request wiring, response-size cap,
invoke_skill/skill_chain cost_logs wiring) all shipped** — verified 2026-08-01 by
`git log` (`3e5b765`, `e795ad0`, `8d03dc6`) and file presence
(`core/effort_adapter.py`, `core/response_budget.py`). This section was stale; the
branch fully landed. No remaining work here.

---

## Open items (resume here)

### Next-roadmap backlog (from the 2026-07-23 vision review, 3 of 6 items shipped 2026-07-24)
Effort key: S = <1 day, M = 1-3 days, L = multi-day/needs its own spec.

| Task | Outcome | Effort | Status |
|---|---|---|---|
| Per-project data scoping (`cost_logs` migration) | **Done** (2026-08-03) — `cost_logs.project_id` (nullable, auto-migrated onto existing DBs via `_ensure_cost_logs_project_id`), `record_cost`/`raw_cost_logs` take `project_id`, new `project_cost_report` tool. Dashboard-side enforcement against `Identity.projects` still not wired — that's the "~30 call sites" part, deferred until a caller actually needs project-scoped auth, not just data. | L | **Done** (schema+API; dashboard enforcement not yet wired) |
| Cross-agent preflight pipeline: rewrite+security+task-type+routing in one pass, adaptive last-2/3-model shortlist | **Done** (2026-08-03, sign-off on shortlist visibility 2026-08-04) — `core/preflight.py::run_preflight`, wired into `userpromptsubmit_policy`. Model shortlist defaults to **adaptive**: surfaces only at "powerful" tier (same trigger the existing tier advisory already uses), so fast/balanced-tier prompts stay exactly as quiet as before — no separate always-on/off toggle needed. `PROMPTWISE_MODEL_RETENTION=on/off` still overrides explicitly for either extreme. `ModelRegistry.top_n_current()`; `doctor` gained a model-catalog-staleness advisory check. Cross-provider suggestion is advisory-text-only, no dispatch (`transports/http.py`'s provider calls are simulated stubs, not real network — real dispatch is a separate credential/network-egress decision, explicitly not built). See `docs/superpowers/specs/2026-08-03-preflight-pipeline-design.md`. | M | **Done.** |
| Remote/mobile MCP access | `dashboard/auth.py`'s own docstring: "the MCP tool layer has no inbound listener and is intentionally out of scope" — a deliberate existing architecture decision, not an oversight. Needs a new network-facing transport (`server.py` is stdio-only today) + auth model + hosting decision before any build starts. | L | Not started — flagged, needs explicit sign-off before scoping |
| Deepen `sync_agent_config`/`check_portability`/etc. across Cursor, Copilot, Windsurf | **Done** (2026-08-01) — `agent_detector.py`'s `detect_agents()` now probes windsurf (`.windsurfrules`), jetbrains (`.aiassistant/` dir), cline (`.clinerules`), aider (`CONVENTIONS.md`, SECONDARY confidence — shared community filename, not unique to aider), goose (`.goosehints`), openhands (`.openhands/microagents/repo.md` PRIMARY or `.openhands/` dir SECONDARY). No probe added for grok — it has no marker file of its own (reads CLAUDE.md/AGENTS.md natively), so it's correctly undetectable as a distinct target; a CLAUDE.md hit already surfaces as "claude". 9 new tests. | M | **Done.** |
| Broader self-learning coverage | `suggest_technique` gains a third outcome-learning axis (categorical, not a ladder — `core/technique_adapter.py`), mirroring the tier/effort pattern | M | **Done** (v1.8.0) |
| Gap-closure P2 (remaining governance items) | Re-scoped 2026-07-24 — see breakdown table below | Split, see below | Re-scoped |
| Session-level cost rollup | `session_cost_report` tool, real per-process `CURRENT_SESSION_ID` replacing hardcoded `"default"` | S-M | **Done** (v1.9.0) |
| Auto skill-match | `userpromptsubmit_policy` hook now surfaces a matching skill on every prompt automatically | S | **Done** (v1.9.0) |
| Device-scoped routing consent | `check_routing_consent`/`grant_routing_consent`, ask-once-per-device bookkeeping | S | **Done** (v1.9.0) |
| JIT/time-boxed scoped MCP permissions | `core/jit_permissions.py` grant store + `grant_jit_permission`/`revoke_jit_permission`/`list_jit_permissions` tools + `jit_permission_guard` PreToolUse hook (active grant → real auto-approve via new `permit`→`allow` hook action; expired grant → `ask`, reverts to normal prompting, never a permanent hard-block) | M | **Done** (v1.9.1) |
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
| 11 | Session-level (multi-call workflow) cost rollup | **Done** (v1.9.0, `75aa1bb`) — `session_cost_report` tool + real per-process `CURRENT_SESSION_ID` (see backlog table above). This row was left stale after that shipped; the net-result summary below already listed it correctly. | **Done.** |
| 12 | Prompt version rollback + replay against captured traces | **Done** — rescoped: no trace-capture store exists (`AuditLog` is metadata-only, `ExactCache` is TTL-only), so replay runs a registered prompt version through the existing `core/eval_harness.py` rubric-case machinery instead of captured traces. Rollback is insert-only (latest-`ts` row wins, no schema migration). `MemoryManager.get_prompt_version`/`rollback_prompt` (data layer) + `rollback_prompt`/`replay_prompt_version` MCP tools. A real bug (`ORDER BY ts DESC` with no tiebreaker — same-microsecond writes made "most recent" nondeterministic) was found and fixed in review with a `rowid DESC` secondary sort. | **Done.** |
| 13 | JIT/time-boxed scoped MCP permissions | **Done** (v1.9.1) — see the backlog table above. Built via brainstorming → writing-plans → subagent-driven-development; the final whole-branch review caught a real architectural gap the 4 task-level reviews missed (`hook_bridge.run()` had no way to actually auto-approve or hand back to the normal prompt, only silent-allow or hard-deny), fixed by adding `permit`/`ask` hook actions without changing the other 14 existing hooks' behavior. | **Done.** |
| 14 | Injection-detection corpus refresh workflow (offline, human-reviewed — not a live ML classifier) | **Done** (v1.9.2) — `security/corpus_store.py` (append-only sqlite history table), `corpus/injection_corpus.json` (external default corpus), `review_corpus_candidates` MCP tool (dry-run scoring), `promote_corpus_candidates` MCP tool (merge + audit trail). All 5 tests pass; full suite green. | **Done.** |
| 15 | Streaming/partial-output validation with auto-fix | Not started. | **Recommend deprioritize/drop.** Real static-analysis wiring (v1.6.0, `use_static_analysis` on `validate_output`) already covers most of the same ground more simply (real linter output vs. a mid-stream architecture shift); the original plan itself flagged "confirm worth the complexity" before committing effort. |
| 16 | Broaden `sync_agent_config` host coverage: Aider, Goose, OpenHands, Grok CLI | **Done** (2026-08-01) — verified each host's actual native-file convention against current docs before coding (this repo has shipped fabricated-fact bugs before): `CONVENTIONS.md` for aider (not auto-loaded without a `read:` line in `.aider.conf.yml` -- flagged in the emitted file itself), `.goosehints` for Goose, `.openhands/microagents/repo.md` for OpenHands. Grok Build/Grok CLI needed **no new emitter** -- it natively auto-reads `CLAUDE.md`/`AGENTS.md` with zero config, so it's aliased straight to the existing `claude` target (`_TARGET_ALIASES`), same pattern as `codex`→`agents`. `portability_check.py`'s `SUPPORTED_HOSTS` picks the 3 new targets up for free (derived from `TARGETS`). 4 new tests. | **Done.** |
| 17 | Live in-session command interception, extending PreToolUse hooks | **Largely already done**, just not by this plan — `hooks/pretooluse_bash_guard.py` (denies destructive shell commands), `hooks/pretooluse_secret_scan.py`, and `hooks/tool_call_budget.py` (per-session tool-call ceiling) all exist and fail-open. | **Re-scope to a gap-fill audit, not a 6h build.** Check what the original gap analysis specifically wanted that these three hooks don't already cover before sizing anything. |
| 17a | `pretooluse_scan` hard-blocked (exit 2) any Write/Edit the scanner flagged as destructive/risk>=0.7, surfacing as an opaque hook error with no way to proceed or silence it (2026-08-01 bug report) | **Done** (2026-08-01) — `core/hook_bridge.py::pretooluse_scan` now returns `ask` instead of `block` for a flagged write (hands off to Claude Code's normal allow/deny prompt), and logs every finding silently to `.promptwise/security_findings.jsonl` regardless of outcome. Standing exceptions reuse the existing JIT permission store: `grant_jit_permission(signature="SecurityScan:file:<path>")` or `signature="SecurityScan:project:<name>")`. | **Done.** |

**Net result: of the original 8, 2 fold into existing backlog items (10→D, 16→agent-sync
deepening), 1 is already substantially done (17, needs only a small gap-fill audit), 1
should be dropped/deprioritized (15). Of the 3 genuinely independent items, #11 (session
cost rollup) shipped in v1.9.0, #13 (JIT scoped permissions) shipped in v1.9.1, #12
(prompt rollback/replay) shipped 2026-07-25, and #14 (injection-detection corpus refresh
workflow) shipped v1.9.2 — gap-closure list now fully closed (all items #1-#17 done or
explicitly folded/rescoped).**
Brainstorm each independently at kickoff — no shared code between them.

### Feature candidates
The 2026-07-08 gap analysis (`docs/GAP_ANALYSIS_2026-07.md`) produced 8 ranked phase
candidates (A–H). **A, B, C, D, E, F, G, H are all done** (Phases 13–17 above as wave 1,
plus F and H documented above). All candidates closed:
- **D — local-embeddings decision** (semantic cache + hybrid BM25/vector memory +
  fact-supersession) — needed a new pip dependency, breaking the standing
  no-new-deps guardrail. Deferred 2026-07-10; revisited 2026-08-04 with a real
  audience-impact review (solo/indie vs small-mid team vs enterprise) and sized
  against measured numbers (fastembed/ONNX path: ~230MB deps + ~65-130MB model,
  no PyTorch) rather than estimates — **signed off, opt-in only, base install
  unchanged**. Plan: `docs/PHASE19_ROADMAP.md`. Split into D1 (fact-supersession,
  no new dependency) and D2 (embeddings themselves, gated on the sign-off above).
  **Shipped 2026-08-04 as v1.10.0** — fact supersession, local embedding provider,
  semantic cache fallback on `cache_lookup`/`cache_store`, hybrid RRF reranking on
  `query_memory`, new `embedding_status` tool, `[embeddings]` installer extra with
  `--embeddings`/`-Embeddings` install flags. 1038 tests passing, including
  dedicated guardrails for the base-install-unchanged requirement.

See `docs/GAP_ANALYSIS_2026-07.md` for full analysis, and non-goals (fairness-metric
parity, bi-temporal memory). `docs/PHASE19_ROADMAP.md` is D's pre-build plan, matching
the convention Phases 13–17 used before their own implementation started.

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
