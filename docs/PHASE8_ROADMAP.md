# PromptWise — Phase 8 Roadmap

Phase 7 built the intelligence + trust layer but left the learning loop **dormant**:
`adaptive_router` only ever sees outcomes fed by the eval harness (7.3), never real
route traffic (the live-route writer was explicitly deferred in 7.1). And `insights.py`
is a 38-line stub over corrections only. Phase 8 closes both gaps.

Two packages, one parallel wave (file-mostly-disjoint; `server.py` is a shared but
additive touch — git handles it).

Standing guardrails: **local-first, air-gap-safe, no new infrastructure, no new pip
dependencies, no branded model ids (tiers/families only), hooks/recording fail-open,
additive, TDD.**

---

## 8.1 — Live-route outcome writer (close the loop)

**Problem.** `route_request` (server.py:352) routes and records *cost* but never records
a **route outcome** into `OutcomeStore`, so adaptive routing cannot learn from real
usage. The store populates only from evals today.

**Design.**
- In the `route_request` handler, after the route decision, record one row to the 7.1
  `OutcomeStore` (`core/adaptive_router.py`): `task_class` = `f"{intent_detected}/{stakes_detected}"`
  (match how `router.py`/`adaptive_router` derive it), `tier` = the decided tier,
  `model_family`, `cost`. The decision row is written immediately with a `neutral` signal.
- Resolve the **quality signal** when one is available for that decision. Reuse existing
  signals only — quality-gate verdict / `validate_output` / captured correction —
  normalized through `normalize_quality_signal`. Correlate decision → later verdict with
  a lightweight in-process recent-decision map keyed by a short route id (no heavy
  plumbing, no schema change beyond the existing `route_outcomes` table). If a verdict
  arrives, update/record the signal; if none arrives, it stays `neutral`.
- Gated by `PROMPTWISE_ROUTE_RECORDING` (default on). **Fail-open**: any recording error
  is swallowed and never affects the route response.

**Acceptance.**
- A `route_request` call writes a `route_outcomes` decision row (tier, class, family, cost).
- When a quality verdict follows for that decision, its signal is set (met/not_met);
  absence leaves it `neutral`.
- A forced recording error does not change or break the route result (fail-open).
- Disabling the flag suppresses recording. Covered by tests.

## 8.2 — Insights engine

**Problem.** `insights.py` only counts corrections. The rich local telemetry
(`route_outcomes`, `eval_results`, cost logs, `roi_stats`) is never turned into
**actionable, ranked recommendations**.

**Design.** Grow `core/insights.py` into a real engine (keep the existing
`compute_insights` correction view; add a recommendation layer). Query the local stores
and emit structured, ranked recommendations across rule families:
- **Routing:** a `task_class` consistently meeting the bar at a cheaper tier →
  "downgrade class X to tier T" (with estimated $ saved); a class failing at a cheap tier
  → "escalate". Reuse `OutcomeStore.stats` + the same min-sample/bar thresholds as 7.1.
- **Cost:** top cost drivers by class/model/project; spend anomaly vs. the window baseline.
- **Quality:** classes with a declining met-rate or standing eval regressions.
- **Budget:** projected overrun in the window → "raise/lower budget".
- Each recommendation carries: `id`, `category`, `message`, `evidence` (counts/samples),
  `estimated_impact`, `confidence`, and is **min-sample gated**. Deterministic, offline.

**Surfaces (additive).**
- MCP tool + `commands/insights.md` command → returns the ranked recommendations.
- A dashboard panel in `dashboard/web.py` rendering the top recommendations (no CDN).

**Acceptance.**
- Seeded outcome/cost data yields the expected routing/cost/quality recommendations,
  ranked and min-sample gated.
- Empty/thin data → no crash; empty or low-confidence set (fail-open).
- The command/tool returns structured recs; the dashboard renders the panel. Tests.

---

## Wave / parallelization

- 8.1 ∥ 8.2 in isolated worktrees (one wave). 8.2 reads the `route_outcomes` schema that
  already exists from 7.1, so it builds and tests independently (its tests seed the table
  directly) — it does not need 8.1 to land first.
- Shared file: `server.py` (8.1 edits the route handler; 8.2 registers an insights tool)
  — additive, different regions; merge 8.1 then 8.2, full suite green after each.

## Guardrails (both)
- Local-first, air-gap-safe, no new infra, no new deps, tiers/families only.
- Recording and insights are fail-open — they never break a route or crash on thin data.
- One clean commit per package; TDD.
