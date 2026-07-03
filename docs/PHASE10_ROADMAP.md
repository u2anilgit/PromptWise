# PromptWise — Phase 10 Roadmap

Debt paydown + one half-closed loop from Phase 9. No new capability surface; this phase
makes the existing code sound. Two file-disjoint packages, one parallel wave.

Standing guardrails: **local-first, air-gap-safe, no new infra, no new deps,
tiers/families only, additive/behavior-preserving, TDD.**

---

## 10.1 — Refactor `call_tool` into a handler registry

**Problem.** `server.py`'s `call_tool` is a single ~1000-line function with an 83-branch
`if/elif name == ...` dispatch — flagged as a complexity risk across Phases 7, 8, and 9.
It is hard to read, hard to review, and every new tool grows the same giant function.

**Design (behavior-preserving — this is the hard rule).**
- Replace the `if/elif` chain with a `name -> handler` registry (dict). Each handler is a
  small function/coroutine `handler(ctx, arguments) -> str` holding exactly the body that
  the corresponding branch has today — same inputs, same return string, same side effects.
- Keep the existing outer `try/except` and any shared pre/post logic (e.g. error framing)
  in `call_tool` around the registry lookup, so error behavior is identical.
- No tool is added, removed, renamed, or changed in behavior. The registry is populated
  from the same names currently dispatched. Unknown-name handling stays identical.
- Group handlers sensibly (by section comment already present) but do NOT change any
  handler's logic while moving it. Pure mechanical extraction + a lookup.

**Acceptance.**
- The full existing test suite passes unchanged (it exercises the tools) — this is the
  behavior-preservation proof.
- The plugin tool-count/surface test still passes (same set of tool names registered).
- `call_tool` is now a thin dispatcher over the registry; no single giant if/elif remains.
- A tiny new test asserts the registry covers every advertised tool name (no dispatch gap).

## 10.2 — Wire the budget overlay into `BudgetGuardian`

**Problem.** Phase 9's governor `AdjustBudgetGuard` writes a new limit to
`.promptwise/budget.local.yaml`, but nothing reads it — `BudgetGuardian` still uses only
its constructor default, so the governor's budget action has no runtime effect. The loop
is half-closed.

**Design.**
- On construction, `BudgetGuardian` reads the local gitignored overlay
  `.promptwise/budget.local.yaml` (the exact file + format the governor writes) and, if a
  limit is present, uses it as the effective `limit_usd` (overlay overrides the default;
  an explicit constructor arg still wins over the overlay so callers can force a value).
- **No import of `core/governor`** (avoid a plugin→core cycle): read the small YAML
  overlay directly with the same loader the rest of the codebase uses, matching the
  governor's write format exactly.
- Fail-soft: a missing/malformed overlay leaves the constructor default in place.

**Acceptance.**
- With an overlay present, a new `BudgetGuardian` uses the overlay's limit; with none, it
  uses the constructor default.
- An explicit `limit_usd=` arg overrides the overlay.
- A malformed/absent overlay never raises — falls back to the default.
- End-to-end: governor `AdjustBudgetGuard` (apply mode) writes the overlay, and a freshly
  constructed `BudgetGuardian` then reflects the new limit. Covered by tests.

---

## Wave / parallelization
- 10.1 (`server.py`) ∥ 10.2 (`plugins/budget.py`) — disjoint files, one wave.
- No shared file. Merge either order; full suite green after each.

## Guardrails
- 10.1 is behavior-preserving: the existing suite is the contract; do not change tool logic.
- 10.2 is additive + fail-soft; no new dependency; no core import from the plugin.
- One clean commit per package; TDD.
