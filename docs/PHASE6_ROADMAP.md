# PromptWise — Phase 6 Roadmap (WP6 & WP7)

Extends the Phase 6 plan. WP1 (lifecycle loops), WP2 (shell/subagent enforcement),
and WP5 (responsible-AI advisory) are already committed. WP3 (command/agent surface)
and WP4 (parallelism) remain as previously scoped. This document adds two packages.

Both are **local-first, no new infrastructure**, and reference model **tiers and
families**, never branded ids in code.

Order: **WP6 first** (stale routing/pricing is a correctness bug), then **WP7** (UX).

---

## WP6 — Dynamic model + auto-pricing resolver

> **Status: implemented.** `config/models.yaml` registry + `core/model_registry.py`
> resolver landed; `router.py` no longer hardcodes any model id. The stale
> `claude-opus-4-7` literal is gone — `powerful` now resolves to the current
> `claude-opus-4-8` from the registry, with its price applied automatically. The
> opt-in daily online refresh below remains future work.

### Problem (grounded)
Routing is static. `src/promptwise/core/router.py:16-19` hardcodes concrete model ids
(`_HAIKU_MODEL`, `_OPUS_MODEL`, `_DEFAULT_MODEL`, `_ALL_MODELS`), and `_pick_model` /
`resolve_model` / `fallback_models` fall back to those literals. `pricing.yaml` is keyed
by frozen model id. When a new model ships, nothing updates — routing and pricing both
require a hand-edit. Unlike WP1/WP2/WP5 this touches a core engine, so it is **not**
purely additive.

### Design — tier → family → newest `current` alias
- **New registry `config/models.yaml`.** One row per model:
  `{ family, tier (fast|balanced|powerful), alias, status: current|deprecated,
  release_date, price_input, price_output, price_cached }`.
  Pricing keyed by **family**, not a frozen id.
- **`router.py` resolves dynamically:** tier → family → newest `current` alias by
  `release_date`. No literal model id remains in routing logic. New model = add or flip
  one registry row; routing follows automatically.
- **Pricing follows the registry.** Cost lookups resolve family → current prices, so a
  new model or a price change is a one-row edit, not a code change.
- **Deprecated ≠ deleted.** `status: deprecated` retires a model from *selection* but
  keeps it for *historical display and label resolution* (see WP7). A model that
  disappears from the host still renders correctly in old stats.
- **Opt-in online refresh, off by default.** An explicit refresh may update
  `status` / `release_date` / prices from the provider's published list. When offline
  (default), the registry is authoritative — air-gapped operation preserved.
  - **Shape (when built):** trigger on the already-wired `SessionStart` hook, guarded by
    a 24h cache stamp (`.promptwise/models_refreshed.json`) so it fetches at most once a
    day; gate the network call behind an explicit flag (`PROMPTWISE_MODEL_REFRESH=on`);
    fail-open — a refresh error keeps the current registry. Discovery caveat stands: the
    provider list is the only source; the host build's exposed models can't be enumerated
    offline, so that remains a one-row registry edit.

### Correctness rules
1. **Point-in-time pricing.** Each usage record stores the unit prices used *at that
   time*. Never recompute historical cost with current prices — keep a `price_history`
   per family; auto-updates affect only new usage.
2. **Immutable model identity in records.** Records reference the alias/family used then;
   the registry resolves display labels even after deprecation.

### Honest caveat
There is no standard host call to enumerate the models a given build exposes offline, so
*fully* automatic discovery is not cleanly available. The resolver + updatable registry is
the realistic equivalent: version change → new routing is a one-row edit (or automatic
with online-refresh on), instead of a code edit.

### Files
- `+ config/models.yaml` — the registry (new).
- `~ src/promptwise/core/router.py` — replace hardcoded ids with a resolver (core edit).
- `~ pricing.yaml` — re-key pricing by family; add `price_history`.
- `~ src/promptwise/config.py` — load the registry; expose family/alias resolution.
- `+ tests/test_model_resolver.py`.

### Acceptance criteria
- Given two `current` models in one family, the newer (`release_date`) alias is chosen.
- A `deprecated` model is never selected by routing.
- Cost for a family resolves to that family's current prices; historical records keep
  their point-in-time prices unchanged after a price update.
- No branded/literal model id remains in `router.py` selection logic.
- Offline run works with the registry alone (online refresh stays off unless opted in).

---

## WP7 — Dashboard modernize + configurable retention (up to 1 year)

> **Status: implemented.** `dashboard/retention.py` (windows, rollups, the metric
> model incl. the net-savings North Star + governance summary), a modernized
> windowed `dashboard/web.py` (7/30/60/90 hot, 180/365 archive; no CDN), a
> `lines` column + `raw_cost_logs` accessor on the store, and changed-line capture
> in the audit hook. The `usage_daily` persisted-rollup *table* is deferred —
> rollups are computed on read, which is fast at this scale; persist them only if
> a year of raw rows ever gets slow.

### Problem (grounded)
`src/promptwise/dashboard/web.py` is a self-contained Flask app (inline HTML, no CDN)
with four static cards and no date-range control. ROI/usage data already lives in the
`roi_stats` table (`ts` column, `db/models.py:70-79`) and the audit JSONL, so this is
presentation + a time filter + a rollup, not new plumbing.

### Retention — two tiers in the same local SQLite file (no infra)
| Tier | Holds | Window | Purpose |
|------|-------|--------|---------|
| **Hot** (raw events) | every call/edit, full detail | 0–90 days, configurable (7/30/60/90) | drill-down, per-event audit |
| **Archive** (`usage_daily` rollup) | one row per `day × model × project × skill`: cost, tokens, calls, lines, blocks | 90 days–1 year | trends, totals, model-mix history |

- A `SessionEnd` rollup upserts `usage_daily`; raw events older than the hot window
  compact into rollups and prune. A year of rollups is a few thousand tiny rows — fast,
  no infra.
- The user sees a **continuous timeline up to 1 year**; only *granularity* drops past 90
  days. Model changes never remove history — deprecated models stay visible (WP6 rule 2).

### UI
- **Date-range selector**: default **30 days**; options 7/30/60/90 on hot data, plus
  archive views out to **1 year**. Windowing pushed into the stats query (filter by
  `ts`), never filtered in the browser. The >90-day cap applies to *raw* granularity only.
- **Modern responsive layout**, served by the existing local server — no external UI
  framework or CDN. Summary cards, a trend chart, and sortable breakdown tables.
- **Configurable stats**: window, grouping (model / project / skill), and metric
  visibility persist to a local prefs file — no rebuild to change the view.
- **Governance panel** surfaces this phase's new signals: enforcement blocks, denied
  shell commands, responsible-AI advisories, failure captures, audit-chain status. The
  dashboard becomes the single "is governance working" view.

### Recommended metrics
✅ = data already exists · ➕ = needs a small capture addition.

**Headline cards (selected window)**
- ✅ Total cost (USD) · ✅ total tokens (input / output / **cached** split)
- ✅ Tokens saved (compression + caching + batching) and **% saved**
- ✅ ROI ratio + estimated time saved · ✅ sessions/tasks + avg cost per session
- ➕ **Lines of code added/changed** — small counter in the PostToolUse audit hook
  (count lines in `new_string`/`content`); audit currently records files, not line counts.

**Trends (full window incl. archive)**
- ✅ Daily/weekly spend · ✅ **model mix over time** (stacked, deprecated models retained)
- ✅ Tokens & cache-hit rate over time · ➕ lines coded over time

**Breakdowns (sortable tables)**
- ✅ Per-model (incl. retired): cost, calls, tokens, avg cost/call
- ✅ Per-project and per-skill: cost, calls, ROI
- ✅ **Routing efficiency**: actual spend vs. cost if all ran on the top tier =
  "savings from smart routing" (defensible headline number)

**Governance panel (new)**
- ✅ Blocked writes · denied shell commands · responsible-AI advisories · failure
  captures · audit-chain status + record count

**Efficiency composites (best single-number options)**
- **Cost per completed task** (down = improving)
- **Savings rate** = tokens-saved % × routing savings (clearest value metric)
- **Cache hit rate** · ➕ **cost per 100 lines changed**

### Files
- `~ src/promptwise/dashboard/web.py` — windowed endpoints + modern UI.
- `~ src/promptwise/db/models.py` — add `usage_daily` rollup table.
- `+ src/promptwise/dashboard/retention.py` — rollup + prune (hot→archive).
- `~ hooks/posttooluse_audit.py` (+ `hook_bridge`) — capture changed-line counts.
- `+ tests/test_retention.py`, `~ tests/` dashboard tests.

### Acceptance criteria
- Default view = last 30 days; selector switches 7/30/60/90; queries filter by `ts`.
- Usage older than the hot window is served from `usage_daily` up to 1 year; totals
  across the boundary are continuous.
- Historical cost uses point-in-time prices (WP6 rule 1); deprecated models still render.
- Governance signals (blocks, advisories, failures, chain status) appear on the dashboard.
- No external CDN/framework; served entirely by the existing local server.

---

## WP4 — Safe-parallelization planner

> **Status: implemented (planner only).** `core/task_graph.py` decides *which*
> tasks are safe to run at once and emits ordered **waves** — the one decision the
> agent harness can't make for itself. Dispatch, result fan-in, and file-write
> isolation stay with the harness (native parallel subagents + worktrees), so this
> is additive and non-breaking.
>
> Rails: Kahn-layered waves; cycle detection (unscheduled tasks are reported, never
> misordered); shared-file serialization (two writers of one file never share a
> wave); fan-out cap (parallelism can't blow the budget). Actual concurrent
> execution is emitted-not-run — the parent turn dispatches each wave. Full-fat
> worktree/agent-team coordination remains deferred; the planner is the durable,
> reusable core of it.

## Metric priority (WP7) — North Star first, not a flat list

The metric menu above is comprehensive; this is the decision on what leads.

**North Star — one hero number: Net savings this window (`$` and `%`).**
`= (baseline cost if every call ran top-tier with no cache) − actual spend`.
Folds routing + caching + compression + batching into the single figure that
justifies the tool. Everything else supports it.

**Headline cards — exactly four:**
1. Total cost (USD) — input / output / **cached** split
2. Tokens saved **%**
3. **Cost per completed task** — the efficiency trend that matters (down = better)
4. Governance status — audit chain OK + block/denial count

**Trends:** spend/day · **model mix over time** (visual proof routing works;
deprecated models retained) · cache-hit rate.

**Governance panel:** blocked writes · denied shell · responsible-AI advisories ·
failure captures · audit-chain status.

**Prune (credibility cost outweighs value):**
- *Estimated time saved* / *productivity score* (`plugins/roi.py`) — invented
  multipliers; keep out of the hero row.
- *Lines of code as a KPI* — vanity and gameable. Keep it **only as a
  denominator** (`cost per 100 lines changed`) and as context, never as a
  success metric.

**Best composite:** `cost per completed task` (or per session) — clearest
efficiency signal; trending down means the routing/caching stack is working.

## Guardrails (both packages)
- No new infrastructure; local-first and air-gapped-safe.
- No branded/competitor/third-party names in code, config, or UI — tiers and families only.
- WP6 is a core-engine edit (not additive) — land it alone, with tests, in its own session.
- WP7 is additive apart from the audit-hook line counter; keep hooks fail-open.
- One package per session, committed and verified before the next.
