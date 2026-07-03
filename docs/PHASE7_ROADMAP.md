# PromptWise — Phase 7 Roadmap

Phase 6 built the governance **surface** (routing, pricing, dashboard, parallel
planner, local runtime, scaffolding). Phase 7 builds the **intelligence and trust**
layer on top of it. Four packages, run as two waves.

All packages keep the standing guardrails: **local-first, air-gap-safe, no new
infrastructure, additive where possible, hooks fail-open, no branded/competitor model
ids in code (tiers and families only).**

## Wave plan (safe parallelization — WP4 rule: shared-file writers never share a wave)

| Pkg | Name | Wave | Writes `router.py`? | Writes `db/models.py`? |
|-----|------|------|--------------------|------------------------|
| 7.1 | Adaptive learning loop | 1 | yes | yes (feedback table) |
| 7.2 | Compliance evidence export | 1 | no | no |
| 7.4 | Platform-reach hardening | 1 | no | no |
| 7.3 | Eval + regression harness | 2 | no (reads) | yes (eval table) |

Wave 1 = 7.1 ∥ 7.2 ∥ 7.4 (disjoint files). Wave 2 = 7.3 (depends on 7.1 outcome
signal and the same choke-point files).

---

## 7.1 — Adaptive learning loop

**Problem.** Routing is static heuristics (tier by intent/stakes). `learning_store`,
`learning_replay`, `capture_learning`, `roi_stats`, and cost logs all exist but never
feed back into a routing decision. PromptWise does not get smarter from its own history.

**Design.**
- New outcome store: per route decision record `{task_class, tier, model_family, cost,
  quality_signal, ts}`. Quality signal sourced from existing signals — quality-gate
  verdict, `validate_output`, captured corrections/failures — normalized to met/not-met
  a bar. Fail-open: absence of a signal is neutral, never negative.
- New `core/adaptive_router.py`: given a task class, blend the static tier pick with a
  learned prior. Prefer the cheapest tier that historically met the quality bar for that
  class. Use bounded, stable estimation (smoothed counts / Beta-style), a minimum-sample
  threshold before it influences anything, and a tier floor it can never route below.
- `router.py` calls the adaptive scorer, keeps static as the default when data is thin.
  Gated by `PROMPTWISE_ADAPTIVE_ROUTING` (default on, fail-open to static on any error).
- Explainable: the route reason names the evidence ("N past tasks of this class met the
  bar at this tier").

**Acceptance.**
- With no history, routing is identical to today (pure static).
- After enough same-class outcomes at a cheaper tier meeting the bar, routing shifts to
  that tier for that class; a class that keeps failing at a cheap tier escalates.
- The scorer never routes below the configured floor and never selects a deprecated model.
- Any scorer error falls back to static routing (fail-open). All behavior covered by tests.

## 7.2 — Compliance evidence export

**Problem.** The audit trail is a local hash-chained JSONL. There is no way to hand an
auditor a self-verifying evidence bundle.

**Design.**
- New `core/compliance_export.py` + a command. Verify the existing hash chain, package
  the records with a manifest (range, counts, chain head digest) into a single bundle
  (JSON, optionally zipped).
- Sign the bundle with a local HMAC key (env var or key file; stdlib `hashlib`/`hmac`
  only). A verify path re-checks signature + chain and reports any tamper with the first
  broken link.
- Optional generic control-family tagging (no branded framework names).

**Acceptance.**
- Export produces a bundle whose verify passes on untouched data and fails, pointing to
  the first broken record, on any mutation.
- No network, no new dependency. Works air-gapped. Covered by tests.

## 7.4 — Platform-reach hardening

**Problem.** Emitters exist (`config_emitter`, `codex_validator`, AGENTS.md/SKILL.md)
but there is no single check that the governance/optimization surface stays consistent
across the hosts we claim to support.

**Design.**
- A portability check that validates the emitted configs for each supported host are
  present, well-formed, and in sync with the skill/agent surface; report drift.
- A generic CI-snippet emitter (host-neutral) so the same governance gates can run in a
  pipeline. Additive; touches emitters/validators + docs only.

**Acceptance.**
- The check flags a missing or stale emitted config and passes when all are in sync.
- Emitted CI snippet is host-neutral and references tiers/families only. Covered by tests.

## 7.3 — Eval + regression harness (Wave 2)

**Problem.** `eval_prompt_across_models` / `run_eval` exist as thin stubs. There is no
durable way to pin expected behavior and catch quality drift across model versions.

**Design.**
- New `core/eval_harness.py` + a command. An eval case = prompt + rubric/expected. Run
  across tiers using the on-device runtime (WP8) when available; offline default is a
  record/dry-run mode that never requires cloud. Score with `validate_output`/quality,
  store results, and diff against a stored baseline to flag regressions; expose a gate.
- Integration point: eval outcomes feed the 7.1 outcome store, closing the loop.

**Acceptance.**
- A case with a known-good baseline passes; a deliberately regressed output is flagged.
- Runs offline with no cloud dependency (record mode or local runtime). Covered by tests.

## Guardrails (all packages)

- Local-first, air-gap-safe, no new infrastructure.
- No branded/competitor model ids — tiers and families only.
- 7.1 and 7.3 touch core engine/schema: land each with tests, integrate one at a time,
  full suite green before the next merge.
- Hooks stay fail-open. One clean commit per package.
