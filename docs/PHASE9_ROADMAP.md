# PromptWise — Phase 9 Roadmap

Phase 8 made PromptWise *see* what to change (the insights engine over a populated
outcome store). Phase 9 lets it *act* — but only inside hard safety rails. This is the
one phase where a bug can change user state, so the design is conservative by default.

**One package** (`core/governor.py` + surfaces). Not parallelized: acting autonomously
is safety-critical and the parts are coupled — it lands alone, with deep tests, default
**off**.

Standing guardrails plus autonomy-specific ones: **local-first, air-gap-safe, no new
infra, no new deps, tiers/families only. Default advise-only. Allowlisted actions only.
Every applied action reversible via an undo ledger. Every proposal, gate verdict,
application, and undo appended to the hash-chained audit log. No destructive or
irreversible auto-action, ever. Fail-safe: any error aborts the action leaving no
partial state.**

---

## 9 — Autonomous governance (the governor)

**Idea.** Turn insights recommendations into typed, policy-gated, reversible actions
that PromptWise can propose (and, only when explicitly enabled, apply) — with a full
audit trail.

**Modes** (env `PROMPTWISE_AUTONOMY`, default `advise`):
- `advise` — propose actions, apply nothing. (default)
- `dry_run` — simulate each action, log the intended effect, apply nothing.
- `apply` — execute allowlisted, reversible actions only; everything else stays advisory.

**Design — `core/governor.py`:**
- `propose(recommendations) -> list[Action]`: map each insights recommendation
  (`compute_recommendations`) to a typed `Action` with a concrete, reversible effect and
  a blast-radius tag (`safe` | `advisory-only`).
- **Policy gate.** Each action is evaluated with the existing `Policy.evaluate_action`
  (reuse `core/policy.py`). A violated action is blocked — never applied — and recorded
  as blocked. Warnings are surfaced, not fatal.
- **Allowlist.** Only these action types can ever move state, and only in `apply` mode:
  - `AdjustBudgetGuard` — write a new budget limit to a local, gitignored overlay
    (never edits tracked config); prior value saved to the undo ledger.
  - `WriteRoutingPreferenceNote` — record a routing-preference nudge as a local advisory
    artifact (non-destructive).
  Everything else (e.g. permission-rule changes from `permission_tuner`, anything that
  touches live `mcp.json`/permissions) is **`advisory-only`**: emitted as a proposal
  artifact for a human to apply, never auto-applied regardless of mode.
- **Undo ledger.** A local store (stdlib sqlite/json) recording `{action_id, type,
  prior_state, new_state, ts}`. `undo(action_id)` restores `prior_state` and is itself
  audited. Applies are idempotent (re-applying the same action is a no-op).
- **Audit.** `propose` / `blocked` / `applied` / `undone` each append to `AuditLog`
  (`core/audit_log.py`) so the chain verifies and the dashboard governance panel can show
  what the governor did.

**Surfaces (additive):**
- MCP tool `run_governor` (returns proposals + verdicts + what would/did apply for the
  current mode) and `governor_undo(action_id)`; a `commands/governor.md` command.
- A governance-actions panel in `dashboard/web.py` (inline HTML, no CDN) listing recent
  proposals, their policy verdict, applied/undo state.

**Acceptance:**
- `advise` (default): proposes actions, applies nothing, logs each proposal; audit chain
  verifies.
- Policy gate: an action that violates policy is blocked, not applied, and recorded as
  blocked with the reason.
- `apply`: only allowlisted reversible actions apply; each writes an undo-ledger entry;
  `undo` restores the exact prior state; re-apply is a no-op (idempotent).
- An `advisory-only` action is never auto-applied in any mode — only emitted as a proposal.
- Any injected error during apply aborts that action with no partial state and no ledger
  entry (fail-safe); other actions are unaffected.
- Everything is offline and audited. Covered by tests.

## Guardrails
- Default advise-only; `apply` requires the explicit env opt-in.
- Allowlist is the only path to state change; destructive/irreversible actions are
  advisory-only, forever.
- Reversible + idempotent + fully audited. Local-first, no new infra/deps, tiers/families
  only. One clean commit; deep TDD (this phase earns extra edge-case coverage).
