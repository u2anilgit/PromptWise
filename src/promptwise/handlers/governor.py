"""handlers.governor -- autonomous governor MCP tool handlers (moved
verbatim from server.py's "Autonomous governor (Phase 9)" section during
the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool, _get_audit_log


@tool(name="run_governor", description="Turn local insights recommendations into typed, policy-gated, REVERSIBLE governance actions. Default advise-only: proposes actions + policy verdicts and reports what would/did apply for the current mode (env PROMPTWISE_AUTONOMY in {advise,dry_run,apply}). Only allowlisted 'safe' actions (AdjustBudgetGuard, WriteRoutingPreferenceNote) can ever move state, and only in apply; each writes a local undo-ledger entry. Everything else is advisory-only. Offline; fully audited.",
         schema={"type": "object", "properties": {
             "window_days": {"type": "integer", "default": 30, "minimum": 1, "maximum": 365},
             "mode": {"type": "string", "enum": ["advise", "dry_run", "apply"], "description": "override PROMPTWISE_AUTONOMY for this call; omit to use the env (default advise)"},
             "root": {"type": "string", "default": ".", "description": "project root holding the gitignored .promptwise overlay + ledger"},
             "policy_path": {"type": "string", "default": "config/policy.yaml"}}})
async def _handle_run_governor(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.governor import Governor
    from promptwise.core.insights import compute_recommendations
    root = arguments.get("root")  # None -> governor's shared home state dir (BudgetGuardian reads there)
    policy_path = arguments.get("policy_path", "config/policy.yaml")
    gov = Governor(root=root, mode=arguments.get("mode"),
                   policy_path=policy_path, audit_log=_get_audit_log())
    recs = compute_recommendations(window_days=arguments.get("window_days", 30))
    return json.dumps(gov.run(recs))


@tool(name="governor_undo", description="Reverse a previously-applied governor action by id, restoring the exact prior state from the undo ledger (audited). No-op if the id is unknown or non-reversible.",
         schema={"type": "object", "properties": {
             "action_id": {"type": "string"},
             "root": {"type": "string", "default": "."}},
         "required": ["action_id"]})
async def _handle_governor_undo(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.governor import Governor
    gov = Governor(root=arguments.get("root"), audit_log=_get_audit_log())
    return json.dumps(gov.undo(arguments.get("action_id", "")))
