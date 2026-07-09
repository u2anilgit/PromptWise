# PromptWise — Phase 16 Roadmap

Candidate **E — Non-technical / organizational UX** from
`docs/GAP_ANALYSIS_2026-07.md` §6. PromptWise's dashboard already beats
CLI-only competitors; this phase closes the remaining "at-a-glance / hands-off"
gaps a non-technical stakeholder (compliance officer, finance, an engineer who
doesn't want to run a CLI) would hit: no alerting, no scheduled report, a
multi-step manual install, and no terminal presence outside the web tab.

Standing guardrails: **local-first, air-gap-safe by default, no new pip
dependencies, no branded/competitor model ids, hooks/autonomy fail-open/safe,
additive where possible, TDD, one clean commit per package.** Alerting in
particular must be **opt-in and off by default** — never phone home unprompted.

---

## 16.1 — Alerting (`core/alerts.py`)

Slack/webhook/email notification when a budget or security threshold is
crossed. Stdlib only: `urllib.request` for a webhook/Slack POST, `smtplib` +
`email.message` for mail — no vendor SDK.

**Zero edits to `plugins/budget.py` or `security/scanner.py`.** Both already
return typed results (`BudgetStatus`, `SecurityResult`) from `check()`. Alerting
is a pure subscriber over those *existing outputs* — `notify_budget(status)`
and `notify_security(result)` take the dataclass a caller already has and
decide whether to fire, with zero coupling back into the modules that produced
them. Call sites (added, additive):

- `server.py`'s `monitor_budget` / `budget_report` handlers, after computing
  the result.
- `server.py`'s `security_check` / `scan_response` / `run_security_suite`
  handlers, after computing the result.
- `core/hook_bridge.py`'s `pretooluse_scan` (already calls
  `SecurityScanner().check()` on every guarded Write/Edit) — the push path.

Every send is wrapped fail-soft: a network error, a bad webhook URL, or a
missing SMTP config never raises and never blocks the governed action that
triggered it (same fail-open contract as the rest of `hook_bridge.py`).

Config: `config/alerts.example.yaml` — ships `enabled: false`. Copy to
`config/alerts.yaml` (gitignored-friendly) to opt in; channel secrets (webhook
URL, SMTP password) are read from environment variables, never committed.

## 16.2 — Scheduled report export (`core/report_export.py` + `core/scheduler.py`)

A periodic summary (spend, security-scan verdicts, governance/governor
actions) for a compliance officer who doesn't touch a CLI, following
`core/compliance_export.py`'s shape: a pure `build_report()` over already-typed
inputs, then a renderer. **No PDF dependency** — exports Markdown or a
self-contained HTML file (same "stdlib templating" approach `dashboard/web.py`
already uses for its own HTML).

`gather_report_data()` assembles the three sections fail-soft per source (the
same convention `rank_context` established in Phase 12 — a broken source drops
its section, never fails the call):
- **Spend** — reads `cost_logs` directly via sync `sqlite3` against the shared
  local DB (`db.models.get_db_path()`), no new store.
- **Security** — `core/security_log.SecurityScanStore` (already the durable
  record of `run_security_suite` verdicts).
- **Governance** — the project-local audit chain (`core/audit_log.AuditLog`)
  plus the governor's `governor_proposals.json` advisory artifact (both
  already written by Phase 9/hook_bridge).

Scheduling: `core/scheduler.py` is a **pull-based due-check**, not a
background daemon — `run_if_due()` compares a small local marker
(`.promptwise/last_report.json`) against a configured interval
(`config/reports.example.yaml`: `interval_hours`, off by default) and
generates+writes a report only when due. This is invoked the same way other
periodic PromptWise behavior already runs: from a hook (`SessionStart`, added
additively alongside the existing `sessionstart_replay` hook) — no persistent
process, no new dependency. A stdlib `sched`/`threading`-based long-running
mode (`run_forever`) is also provided for anyone who wants a real daemon
cadence instead, started explicitly via `promptwise report-scheduler --daemon`
— never started implicitly.

New MCP tool: `export_org_report` (mirrors `export_compliance_bundle`'s
shape — a genuinely new capability, not a natural extension of
`insights_report`/`budget_report`, so it gets its own tool rather than
overloading an existing one per the task's guidance).

## 16.3 — One-line installer (`install.sh`, `install.ps1`)

Conceptually ports the "one command, pip install + MCP config write" idea
`caveman`'s installer popularized — not its code, PromptWise's install shape is
different (Python package + optional Claude Code plugin registration vs.
caveman's own setup). Both scripts:

1. Check `python3`/`python` >= 3.10 is on `PATH`.
2. `pip install -e .` (`--dev` flag installs `.[dev]` for contributors).
3. If the `claude` CLI is present, run the exact two commands `INSTALL.md`
   already documents as manual steps (`claude marketplace add ./`,
   `claude plugin install promptwise`) — automating the Claude Code path.
4. Otherwise, fall back to `core/installer_support.py` (new, stdlib-only,
   unit-tested) to idempotently merge a `promptwise` server entry into a
   target `.mcp.json` for any other MCP host, without clobbering existing
   entries — automating the "any MCP host" manual step from `INSTALL.md`.
5. Print the same verification command `INSTALL.md` already documents.

The shell orchestration is intentionally thin; the only new logic
(`merge_mcp_json`) lives in Python where it's actually testable.

## 16.4 — Statusline badge (`core/statusline.py` + `hooks/promptwise-statusline.*`)

An at-a-glance terminal line — `budget: 40% used | last scan: 2h ago` —
reusing the exact state the dashboard already reads: `BudgetGuardian`'s
effective limit + a sync `cost_logs` sum for spend, and
`core/security_log.SecurityScanStore` for the last scan timestamp. No new
state store.

`core/statusline.py` is import-only (pure `gather_status()` +
`format_statusline()`, both unit-tested); exposed two ways so it works
whether or not the package is `pip install -e`'d: a `promptwise statusline`
CLI subcommand, and `python -m promptwise.core.statusline` directly. The
actual `hooks/promptwise-statusline.sh` (POSIX) / `.ps1` (Windows) files are
thin wrappers that set `PYTHONPATH` relative to the repo and invoke the
module — same pattern the existing `hooks/*.py` scripts use, just from shell.

## Guardrails recap

- Alerting is opt-in and off by default; nothing here phones home unless a
  human configures a webhook/SMTP target.
- No new pip dependency anywhere in this phase (stdlib `urllib`, `smtplib`,
  `sqlite3`, `sched`, `threading`, `json` only).
- `security/scanner.py` and `plugins/budget.py` are untouched — alerting
  subscribes to their existing typed outputs, not their internals.
- Every new I/O path (webhook POST, SMTP send, report generation) is
  fail-soft: an error degrades to a no-op, never raises into the caller.
- TDD, one commit per package (16.1–16.4).
