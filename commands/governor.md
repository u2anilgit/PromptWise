---
description: Propose (and, only when explicitly enabled, apply) policy-gated, reversible governance actions.
argument-hint: [optional window in days, default 30]
---

Use the PromptWise `run_governor` tool to turn local insights recommendations into typed,
policy-gated, **reversible** governance actions. It is **advise-only by default**: it
proposes actions with their policy verdicts and reports what *would* apply — it changes
nothing unless the operator has explicitly set `PROMPTWISE_AUTONOMY=apply`.

Modes (env `PROMPTWISE_AUTONOMY`, default `advise`):
- `advise` — propose + audit, apply nothing.
- `dry_run` — simulate and log the intended effect, apply nothing.
- `apply` — execute **only** allowlisted `safe` actions (`AdjustBudgetGuard`,
  `WriteRoutingPreferenceNote`), each writing a local undo-ledger entry. Everything else
  (e.g. permission-rule changes) stays advisory-only and is never auto-applied.

Summarize the proposals with their type, blast-radius (`safe`/`advisory-only`), policy
verdict, and applied/would-apply status. To reverse an applied action, use `governor_undo`
with its `action_id` — it restores the exact prior state from the ledger. Everything is
offline and appended to the hash-chained audit trail.

$ARGUMENTS
