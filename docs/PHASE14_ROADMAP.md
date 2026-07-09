# PromptWise — Phase 14 Roadmap

Cost correctness + enforcement: fix the `predict_cost` pricing-drift bug,
add provider-level hard budget caps at routing time, and attribute
workflow (tool/API) cost alongside LLM token cost in `plugins/budget.py`.
This is candidate **B** from `docs/GAP_ANALYSIS_2026-07.md` ("5. Cost /
routing / optimization").

Standing guardrails: **local-first, air-gap-safe, no new infra, no new
deps, TDD.**

---

## 14.1 — Fix `predict_cost`'s pricing-dict drift

**Bug** (`GAP_ANALYSIS_2026-07.md` section 3, "Bug" note): `BudgetGuardian.
predict_cost` hardcoded its own `{tier: {input, output}}` price table. It
duplicated `config/models.yaml` (the model registry `core/router.py`
already treats as the source of truth) and had already drifted: haiku's
hardcoded rate was `0.8`/`4.0` per Mtok vs. the registry's live `1.0`/`5.0`.

**Fix:** `BudgetGuardian` now takes optional `config`/`registry`
constructor args (defaulting to `AppConfig()`/`ModelRegistry()`, mirroring
`Router.__init__`) and `predict_cost` reads pricing the *same* way
`Router._input_rate` does: registry price first (the live source), config
pricing second, `RateSpec` defaults last. The two engines share one price
lookup chain and can't independently drift again.

`predict_cost` still accepts a bare tier/family word (`"haiku"`) alongside
a concrete alias, resolving it through the registry (`_FAMILY_TIER` ->
`registry.resolve(tier, "claude")`) — the same leniency the old hardcoded
version had, now backed by live data instead of a frozen dict. The
`recommendation` field keeps the existing `haiku`/`sonnet`/`opus`
tier-name vocabulary (this repo's allowed non-branded vocabulary) via a
small display-only `_TIER_LABELS` map; only the cost *math* changed.

`server.py`'s `BudgetGuardian(...)` construction now also passes
`config=config` so production wiring gets the fully-loaded
`config/promptwise.yaml` (matching what `Router` already receives),
closing the gap for non-Claude models (`gpt-4o` etc.) that only exist in
`promptwise.yaml`'s `models:` block, not `models.yaml`'s registry.

Out of scope: `server.py`'s `_handle_eval_prompt_across_models` has its
*own* separate hardcoded per-tier price table (used only for that tool's
side-by-side estimate). It wasn't named in the gap-analysis bug note and
isn't one of the five budget tools this phase extends — left untouched to
stay in scope.

## 14.2 — Provider-level hard budget cap at routing time

**Gap:** `BudgetGuardian` only ever reported spend *after* the fact
(`check()`/`monitor_budget`). Nothing stopped routing from recommending an
expensive tier for a provider that had already blown its budget. LiteLLM's
`provider_budget_routing` blocks a provider once its configured cap is
hit, before the call is dispatched.

**Fix:** `ProviderConfig` (`config.py`) gains an optional `daily_cap_usd:
float | None = None` field, parsed from an optional `daily_cap_usd:` key
under `providers.<name>` in `promptwise.yaml`. Absent (the default) means
unlimited — zero behavior change for the shipped config, which configures
no caps.

`Router.route()` gains a new optional `provider_spend_usd: float | None =
None` parameter, mirroring the existing caller-supplied
`monthly_budget_usd`/`days_elapsed_in_month` convention already on the
same signature — `Router` owns no spend persistence of its own, by design
(persistence lives in `plugins/budget.py`/the DB layer). When a provider
has a configured cap *and* the caller reports spend at or above it, the
router forces the tier to `"fast"` (cheapest) **before** resolving the
model — a real routing-time refusal of the requested tier, not a
post-call report — and marks `RouteResult.provider_capped = True` with a
human-readable reason. No cap configured, or no spend figure supplied ->
`provider_capped` stays `False`: fail-open, identical to pre-Phase-14
routing.

Wired through the `route_request` MCP tool: a new optional
`provider_spend_usd` input, and `provider_capped` in the JSON response.

**Scope decision:** this enforces a hard $ cap per provider, not the
already-present-but-unused `model_routing.cost_safety.*` percentage
thresholds (`downgrade_at_budget_pct`/`emergency_haiku_pct`/
`hard_stop_pct`/`never_downgrade`) in `promptwise.yaml`. Those are a
separate, global-budget-percentage concept (also currently dead/unwired)
and conflating the two would have widened this phase's scope beyond "add
a provider cap." Left as an explicit non-goal for a future phase to wire
up on its own terms.

**Scope decision:** a capped provider reroutes to its own cheapest tier
rather than being excluded in favor of a *different* provider (LiteLLM's
literal behavior). `Router.route()`'s call shape takes one caller-chosen
`provider` per call, not a candidate list to select among — true
cross-provider failover would be a larger, separate redesign. Downgrading
to the cheapest tier for the requested provider is the faithful mechanical
analogue available within the existing architecture; the calling agent
still sees `provider_capped=True` and can choose a different provider on
its next call.

## 14.3 — Workflow-level cost attribution

**Gap:** `BudgetGuardian.check()` only ever saw one aggregate `used_usd`
figure. There was no way to see how much of a workflow's spend was LLM
token cost vs. tool/API execution cost — LangSmith attributes both per
workflow.

**Fix:** `check()` gains an optional `tool_cost_usd: float = 0.0`
parameter — a second cost leg alongside the existing `used_usd` (LLM
token cost) leg. The two legs are summed for limit/alert/daily-burn/
projection purposes (so tool cost genuinely counts toward the hard stop,
not just LLM spend), and `BudgetStatus` gains a `cost_breakdown:
dict[str, float] | None` field (`{"llm_usd": ..., "tool_usd": ...}`),
populated only when `tool_cost_usd` is nonzero. Every existing caller
(`monitor_budget`, `dashboard/web.py`'s `g.check(used_usd=...,
days_elapsed=...)`) omits `tool_cost_usd` and sees byte-for-byte identical
output — additive, no breaking change.

Wired through the `monitor_budget` MCP tool: a new optional
`tool_cost_usd` input, and `cost_breakdown` in the JSON response.

`predict_cost`/`get_budget_status`/`set_budget_limit`/`budget_report` are
unchanged by this task — `check()`/`monitor_budget` is the tool that
already represented "current workflow spend," so it's the natural single
place to attribute the second cost leg rather than inventing a parallel
API surface.

## Guardrails

- No new dependency, no new persistence, no new ranking/pricing logic —
  `predict_cost` now *reads* the registry `router.py` already reads.
- Provider caps are opt-in (`daily_cap_usd` absent by default) and
  fail-open (no spend figure supplied -> no enforcement).
- `tool_cost_usd` defaults to `0.0` everywhere -> existing callers are
  unaffected.
- TDD throughout, one commit per task (14.1 / 14.2 / 14.3).
