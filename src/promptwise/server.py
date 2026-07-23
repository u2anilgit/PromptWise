"""PromptWise — Unified MCP server with ALL tools."""

import asyncio
import difflib
import importlib
import inspect
import json
import sys
import re as _re
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path = [p for p in sys.path if p not in ("", str(Path.cwd()))]

from promptwise.config import load_config
from promptwise.core import (
    Router, Rewriter, Optimizer, CompressionEngine, CachePlanner,
    Batcher, Summarizer, RoleDetector, Orchestrator, QualityGuard,
    SkillLoader, WorkflowPlanner, TaskTracker, validate_mermaid,
)
from promptwise.security import SecurityScanner, ComplianceEngine
from promptwise.plugins import BudgetGuardian, CodeValidator, CostMonitor, ROITracker
from promptwise.db import init_db, SessionManager, MemoryManager
from promptwise.core.tool_registry import (
    ServerContext, ToolRegistry, _RegistryEntry, _registry, tool,
    _record_route_verdict, _record_effort_verdict, _resolve_effort,
    _record_skill_execution, _get_audit_log,
)


async def list_tools() -> list[Tool]:
    return _TOOL_DEFS


# ── Handler package loading (Tasks 1/2 of handlers/ package split) ──────────
_HANDLER_MODULES: list[str] = []

_HANDLER_LOAD_ERRORS: dict[str, str] = {}


def _load_handler_modules() -> None:
    """Import every handler category currently in _HANDLER_MODULES, in
    isolation. A category that fails to import (bad dependency, syntax
    error, missing optional package) is logged and skipped -- its tools
    simply never register -- rather than crashing the other categories.
    Fits the plugin's existing fail-open convention (route_recorder,
    effort_recorder, response_budget).

    Safe to call more than once: Python's import system caches already-loaded
    modules, so a repeat call is a no-op for any name already imported --
    this lets _add_handler_module() invoke it once per category, at that
    category's original in-file position, without re-registering (or
    re-ordering) categories loaded by an earlier call."""
    import logging
    _handlers_logger = logging.getLogger("promptwise.handlers")
    for _name in _HANDLER_MODULES:
        try:
            importlib.import_module(f"promptwise.handlers.{_name}")
        except Exception as e:
            _HANDLER_LOAD_ERRORS[_name] = f"{type(e).__name__}: {e}"
            _handlers_logger.warning(
                "handler category %r failed to load -- its tools are "
                "unavailable this run: %s", _name, e)


def _disabled_categories() -> set[str]:
    """Categories to skip at import time: config.yaml's
    handlers.disabled_categories, unioned with the
    PROMPTWISE_DISABLED_HANDLER_CATEGORIES env var (comma-separated) for a
    zero-file override. Fail-open to "nothing disabled" on any config
    error, matching every other config read in this codebase."""
    import os
    configured: set[str] = set()
    try:
        from promptwise.config import load_config
        configured = set(load_config().handlers.disabled_categories or [])
    except Exception:
        pass
    env_val = os.environ.get("PROMPTWISE_DISABLED_HANDLER_CATEGORIES", "")
    env_set = {c.strip() for c in env_val.split(",") if c.strip()}
    return configured | env_set


def _add_handler_module(name: str) -> None:
    """Register one handler category at the exact file position its section
    used to occupy, then load immediately -- this is what keeps _TOOL_DEFS'
    registration order identical to the pre-split monolithic server.py (the
    golden snapshot's ordering contract) even though the 18 remaining move
    tasks are executed in a different order than the categories originally
    appeared in the file. Skips (never appends) a category disabled via
    config/env, checked fresh at each call so a later config reload is
    honored the same way the original one-shot filter was."""
    if name not in _disabled_categories():
        _HANDLER_MODULES.append(name)
    _load_handler_modules()


# ─────────────────────────────────────────────────────────────────────────────
# Tool handlers — one coroutine per tool. Bodies moved verbatim from the former
# call_tool if/elif dispatch (Phase 10 WP10.1). Behavior-preserving: same inputs,
# same awaits, same return strings, same side effects.
# ─────────────────────────────────────────────────────────────────────────────


@tool(name="route_request", description="Route request to appropriate model tier based on intent, stakes, and budget",
         schema={"type": "object", "properties": {
             "text": {"type": "string"}, "intent": {"type": "string", "enum": ["auto", "extract", "classify", "summarize", "question", "code", "analysis", "agent_loop", "research"], "default": "auto"},
             "stakes": {"type": "string", "enum": ["auto", "low", "medium", "high"], "default": "auto"},
             "provider": {"type": "string", "default": "claude"}, "monthly_budget_usd": {"type": "number"}, "days_elapsed_in_month": {"type": "integer"},
             "provider_spend_usd": {"type": "number", "description": "Spend already incurred for this provider (e.g. today) -- enables a hard budget-cap reroute before the call, if the provider has a configured daily_cap_usd"}},
         "required": ["text"]})
async def _handle_route_request(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.router.route(
        text=arguments.get("text", ""), intent=arguments.get("intent", "auto"),
        stakes=arguments.get("stakes", "auto"), provider=arguments.get("provider", "claude"),
        monthly_budget_usd=arguments.get("monthly_budget_usd"), days_elapsed_in_month=arguments.get("days_elapsed_in_month"),
        provider_spend_usd=arguments.get("provider_spend_usd"))
    await ctx.memory.record_cost(tool="route_request", session_id="default", model=r.recommended_model, cost_usd=r.estimated_input_cost_usd)
    # Close the learning loop: record the decision as a neutral outcome row
    # (WP8.1). Fail-open — recording never changes or breaks the route.
    route_id = None
    try:
        from promptwise.core.route_recorder import record_route_decision
        reg = ctx.router.registry
        route_id = record_route_decision(
            task_class=f"{r.intent_detected}/{r.stakes_detected}",
            tier=reg.tier_of(r.recommended_model),
            model_family=reg.family_of(r.recommended_model) or "",
            cost=r.estimated_input_cost_usd)
    except Exception:
        route_id = None
    effort = _resolve_effort(r.intent_detected, r.stakes_detected)
    # Close the learning loop for the effort axis too (mirrors route_id above,
    # independent ladder). Fail-open — recording never changes/breaks the route.
    effort_id = None
    try:
        from promptwise.core.effort_recorder import record_effort_decision
        effort_id = record_effort_decision(
            task_class=f"{r.intent_detected}/{r.stakes_detected}", effort=effort)
    except Exception:
        effort_id = None
    # Concrete provider param for the resolved effort (thinking_budget_tokens,
    # reasoning_effort, ...) -- resolve_effort_param never raises.
    try:
        from promptwise.core.effort_map import resolve_effort_param
        effort_param = resolve_effort_param(effort, arguments.get("provider", "claude"))
    except Exception:
        effort_param = {}
    return json.dumps({"recommended_model": r.recommended_model, "reason": r.reason, "intent_detected": r.intent_detected,
                       "stakes_detected": r.stakes_detected, "estimated_input_cost_usd": r.estimated_input_cost_usd,
                       "context_window_pct": r.context_window_pct, "alternatives": r.alternatives,
                       "batch_recommended": r.batch_recommended, "batch_recommendation_note": r.batch_recommendation_note,
                       "provider_capped": r.provider_capped, "monthly_budget_capped": r.monthly_budget_capped,
                       "effort": effort, "effort_param": effort_param, "route_id": route_id, "effort_id": effort_id})


@tool(name="rewrite_prompt", description="Rewrite prompt with role framing and filler removal",
         schema={"type": "object", "properties": {
             "text": {"type": "string"}, "role": {"type": "string", "enum": ["general", "developer", "analyst", "manager", "security", "IT", "designer", "writer", "researcher", "pm"], "default": "general"},
             "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["text"]})
async def _handle_rewrite_prompt(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.rewriter.rewrite(arguments.get("text", ""), role=arguments.get("role", "general"), model=arguments.get("model", "claude-sonnet-4-6"))
    await ctx.memory.record_cost(tool="rewrite_prompt", session_id="default", model=arguments.get("model", "claude-sonnet-4-6"), input_tokens=r.raw_tokens, saving_pct=r.saving_pct)
    return json.dumps({"rewritten": r.rewritten, "saving_pct": r.saving_pct, "warning": r.warning})


@tool(name="optimize_context", description="Compress context to fit token budget by dropping low-value content",
         schema={"type": "object", "properties": {
             "context": {"type": "string"}, "token_budget": {"type": "integer", "default": 2000, "minimum": 100},
             "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["context"]})
async def _handle_optimize_context(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.optimizer.optimize(arguments.get("context", ""), token_budget=arguments.get("token_budget", 2000), model=arguments.get("model", "claude-sonnet-4-6"))
    return json.dumps({"optimized": r.optimized, "saving_pct": r.saving_pct, "chunks_dropped": r.chunks_dropped})


@tool(name="compress_prompt", description="Apply caveman compression: remove articles, filler, pleasantries, hedging",
         schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
async def _handle_compress_prompt(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.compression.compress(arguments.get("text", ""))
    return json.dumps({"compressed": r.compressed, "saving_pct": r.saving_pct, "tokens_saved": r.tokens_saved, "rules_applied": r.rules_applied})


@tool(name="plan_cache", description="Plan cache breakpoints for prompt reuse",
         schema={"type": "object", "properties": {
             "messages": {"type": "array", "items": {"type": "object", "properties": {"role": {"type": "string", "enum": ["system", "user", "assistant"]}, "content": {"type": "string"}, "label": {"type": "string"}}, "required": ["role", "content"]}},
             "expected_reuse_count": {"type": "integer", "default": 2, "minimum": 1}, "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["messages"]})
async def _handle_plan_cache(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.cache_planner.plan(arguments.get("messages", []), expected_reuse_count=arguments.get("expected_reuse_count", 2), model=arguments.get("model", "claude-sonnet-4-6"))
    return json.dumps({"breakpoints": r.breakpoints, "savings_pct": r.savings_pct})


@tool(name="cache_lookup", description="Exact-match lookup in the local result cache (ExactCache): given identical (tool, request) input to a prior cache_store call, return the stored result instead of recomputing. Hash-based only, no embeddings/similarity threshold. Offline.",
         schema={"type": "object", "properties": {
             "tool": {"type": "string", "description": "name of the tool/skill this result belongs to"},
             "request": {"description": "the request payload to hash (string or object)"}},
         "required": ["tool", "request"]})
async def _handle_cache_lookup(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.exact_cache import ExactCache
    r = ExactCache().get(arguments.get("tool", ""), arguments.get("request"))
    return json.dumps(r.to_dict())


@tool(name="cache_store", description="Store a result in the local exact-match cache (ExactCache) for later cache_lookup hits. Refuses to store (reports why) if category is medical/legal/financial/personalized/health, or if the request/result contains PII or secrets per security.scanner. Offline.",
         schema={"type": "object", "properties": {
             "tool": {"type": "string", "description": "name of the tool/skill this result belongs to"},
             "request": {"description": "the request payload to hash (string or object)"},
             "result": {"description": "the result to cache (any JSON-serializable value)"},
             "category": {"type": "string", "default": "", "description": "e.g. 'medical'/'legal'/'financial'/'personalized'/'health' are never cached"},
             "ttl_seconds": {"type": "integer", "description": "override the default 1h TTL; 0 means no expiry"}},
         "required": ["tool", "request", "result"]})
async def _handle_cache_store(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.exact_cache import ExactCache
    r = ExactCache().put(
        arguments.get("tool", ""), arguments.get("request"), arguments.get("result"),
        category=arguments.get("category", ""), ttl_seconds=arguments.get("ttl_seconds"))
    return json.dumps(r.to_dict())


@tool(name="cache_stats", description="Hit/miss/entry-count/hit-rate report for the local exact-match cache (ExactCache), broken down by category. Purges expired entries first by default.",
         schema={"type": "object", "properties": {
             "purge_expired": {"type": "boolean", "default": True}}})
async def _handle_cache_stats(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.exact_cache import ExactCache
    cache = ExactCache()
    if arguments.get("purge_expired", True):
        cache.purge_expired()
    return json.dumps(cache.stats())


@tool(name="batch_prompts", description="Batch multiple tasks into one prompt to reduce overhead",
         schema={"type": "object", "properties": {
             "tasks": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
             "role": {"type": "string", "default": "general"}, "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["tasks"]})
async def _handle_batch_prompts(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.batcher.batch(arguments.get("tasks", []), role=arguments.get("role", "general"), model=arguments.get("model", "claude-sonnet-4-6"))
    return json.dumps({"batched_prompt": r.batched_prompt, "saving_pct": r.saving_pct})


@tool(name="summarize_thread", description="Compress conversation for fresh thread handoff",
         schema={"type": "object", "properties": {
             "conversation": {"type": "string"}, "max_tokens": {"type": "integer", "default": 500, "minimum": 100, "maximum": 2000},
             "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["conversation"]})
async def _handle_summarize_thread(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.summarizer.summarize(arguments.get("conversation", ""), max_tokens=arguments.get("max_tokens", 500), model=arguments.get("model", "claude-sonnet-4-6"))
    return json.dumps({"summary": r.summary, "reset_prompt": r.reset_prompt, "saving_pct": r.saving_pct})


@tool(name="compare_providers", description="Compare cost of same request across providers",
         schema={"type": "object", "properties": {
             "text": {"type": "string"}, "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["text"]})
async def _handle_compare_providers(ctx: ServerContext, arguments: dict) -> str:
    return json.dumps({"comparisons": ctx.router.compare_providers(arguments.get("text", ""), model=arguments.get("model", "claude-sonnet-4-6"))})


def _maybe_alert_budget(status) -> None:
    """Best-effort, opt-in notification hook (Phase 16). Subscribes to an
    ALREADY-COMPUTED BudgetStatus; never touches plugins/budget.py."""
    try:
        from promptwise.core import alerts
        alerts.notify_budget(status)
    except Exception:
        pass


# security_check/prompt_injection/owasp_scan/scan_response/
# benchmark_injection (handlers.security) originally sat right here,
# between list_tools's helpers and Role Detection -- register at this
# position to preserve tool registration order.
_add_handler_module("security")


# plan_workflow/add_task/update_task/list_tasks/task_report/
# validate_mermaid/detect_role (handlers.role_detection) originally sat
# right here, between benchmark_injection and orchestrate_tasks -- register
# at this position to preserve tool registration order.
_add_handler_module("role_detection")


# orchestrate_tasks/run_autonomous (handlers.orchestration) originally sat
# right here, between Role Detection and Budget & Cost -- register at this
# position to preserve tool registration order.
_add_handler_module("orchestration")


# monitor_budget/predict_cost/set_budget_limit/get_budget_status/
# budget_report (handlers.budget_cost) originally sat right here, between
# detect_role and validate_output -- register at this position to preserve
# tool registration order.
_add_handler_module("budget_cost")


# validate_output (handlers.code_validation) originally sat right here,
# between budget_report and track_roi -- register it at this position to
# preserve tool registration order (golden snapshot).
_add_handler_module("code_validation")


# track_roi/get_roi_report/cost_report (handlers.roi) originally sat right
# here, between validate_output and get_memory_context -- register at this
# position to preserve tool registration order.
_add_handler_module("roi")


# get_memory_context/query_memory/ping_session/check_session_timeout
# (handlers.memory_session) originally sat right here, between cost_report
# and invoke_skill -- register at this position to preserve tool
# registration order.
_add_handler_module("memory_session")


# invoke_skill/list_skills/skill_chain/suggest_skill (handlers.skills)
# originally sat right here, between check_session_timeout and
# suggest_technique -- register at this position to preserve tool
# registration order.
_add_handler_module("skills")


# suggest_technique/apply_craft/inject_few_shot/add_chain_of_thought/
# chain_prompts/eval_prompt_across_models/audit_system_prompt
# (handlers.prompt_engineering) originally sat right here, between
# detect_role and save_prompt -- register at this position to preserve
# tool registration order.
_add_handler_module("prompt_engineering")


# save_prompt/search_prompts/compare_prompts (handlers.prompt_registry)
# originally sat right here, between audit_system_prompt and
# get_session_stats -- register at this position to preserve tool
# registration order.
_add_handler_module("prompt_registry")


# get_session_stats/clear_history/export_stats/reload_config
# (handlers.session_data) originally sat right here, between
# compare_prompts and check_energy -- register at this position to
# preserve tool registration order.
_add_handler_module("session_data")


# check_energy/route_for_plugin/run_eval/run_eval_harness/get_sbom/
# run_security_suite/run_red_team_harness (handlers.energy_routing)
# originally sat right here, between reload_config and agile_plan --
# register at this position to preserve tool registration order.
_add_handler_module("energy_routing")


# ── Agile method + governance (additive) ─────────────────────────────
@tool(name="agile_plan", description="Two-phase, persona-aware agile plan (analyst->pm->[ux]->architect->po, then per-story sm->dev->qa loop) layered on the workflow classifier; carries the compliance gate and model-tier routing",
         schema={"type": "object", "properties": {"task": {"type": "string"}, "regulated": {"type": "boolean"}, "brownfield": {"type": "boolean"}}, "required": ["task"]})
async def _handle_agile_plan(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.agile_planner import AgilePlanner
    cfg_path = Path(__file__).resolve().parents[2] / "config" / "agile.yaml"
    plan = AgilePlanner(config_path=cfg_path).plan(
        arguments.get("task", ""), arguments.get("regulated"), arguments.get("brownfield"))
    return json.dumps(plan.to_dict())


@tool(name="shard_doc", description="Split a PRD/architecture markdown document into focused, anchored shards by heading level",
         schema={"type": "object", "properties": {"markdown": {"type": "string"}, "by_level": {"type": "integer", "default": 2}}, "required": ["markdown"]})
async def _handle_shard_doc(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.doc_sharder import DocSharder
    shards = DocSharder().shard(arguments.get("markdown", ""), int(arguments.get("by_level", 2)))
    return json.dumps([s.__dict__ for s in shards])


@tool(name="draft_story", description="Assemble a self-contained, context-engineered story: embeds architecture shards, constraints, and compliance rules inline so the dev executor needs no external lookup",
         schema={"type": "object", "properties": {"story_id": {"type": "string"}, "title": {"type": "string"}, "epic_id": {"type": "string", "default": ""}, "acceptance_criteria": {"type": "array", "items": {"type": "string"}, "default": []}, "arch_shards": {"type": "array", "items": {"type": "object"}, "default": []}, "files_to_touch": {"type": "array", "items": {"type": "string"}, "default": []}, "constraints": {"type": "array", "items": {"type": "string"}, "default": []}, "compliance_rules": {"type": "array", "items": {"type": "string"}, "default": []}, "tasks": {"type": "array", "items": {"type": "string"}, "default": []}}, "required": ["story_id", "title"]})
async def _handle_draft_story(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.story_context import StoryContextBuilder
    story = StoryContextBuilder().build(
        story_id=arguments.get("story_id", ""), title=arguments.get("title", ""),
        epic_id=arguments.get("epic_id", ""),
        acceptance_criteria=arguments.get("acceptance_criteria", []),
        arch_shards=arguments.get("arch_shards", []),
        files_to_touch=arguments.get("files_to_touch", []),
        constraints=arguments.get("constraints", []),
        compliance_rules=arguments.get("compliance_rules", []),
        tasks=arguments.get("tasks", []))
    return json.dumps({"story": story.to_dict(), "markdown": story.to_markdown()})


@tool(name="run_quality_gate", description="Issue an advisory, auditable quality-gate decision (PASS/CONCERNS/FAIL/WAIVED) from findings, risk score, and NFR assessment",
         schema={"type": "object", "properties": {"story_id": {"type": "string"}, "findings": {"type": "array", "items": {"type": "object"}, "default": []}, "risk_score": {"type": "integer", "default": 0}, "nfr_assessment": {"type": "object", "default": {}}, "waiver_reason": {"type": "string", "default": ""}, "route_id": {"type": "string", "description": "Optional: route_id from a prior route_request; folds this gate verdict back onto that route's learning outcome"}, "effort_id": {"type": "string", "description": "Optional: effort_id from a prior route_request; folds this gate verdict back onto that effort decision's learning outcome"}}, "required": ["story_id"]})
async def _handle_run_quality_gate(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.quality_gate import QualityGate
    res = QualityGate().evaluate(
        arguments.get("story_id", ""), arguments.get("findings", []),
        int(arguments.get("risk_score", 0)), arguments.get("nfr_assessment", {}),
        arguments.get("waiver_reason", ""))
    _record_route_verdict(arguments.get("route_id"), res.decision)  # WP8.1 loop close (fail-open)
    _record_effort_verdict(arguments.get("effort_id"), res.decision)  # effort-axis loop close (fail-open)
    return json.dumps(res.to_dict())


@tool(name="check_policy", description="Evaluate a proposed action (model tier, cost, operation, gates) against the cross-agent governance policy; returns allow/block with recorded reasons",
         schema={"type": "object", "properties": {"model_tier": {"type": "string"}, "estimated_cost": {"type": "number"}, "spent_so_far": {"type": "number"}, "operation": {"type": "string"}, "gates_passed": {"type": "array", "items": {"type": "string"}, "default": []}, "policy_path": {"type": "string", "default": "config/policy.yaml"}}})
async def _handle_check_policy(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.policy import Policy
    policy_path = arguments.get("policy_path", "config/policy.yaml")
    try:
        pol = Policy.from_yaml(policy_path)
    except FileNotFoundError:
        return json.dumps({"error": f"policy file not found: {policy_path} (copy config/policy.example.yaml -> config/policy.yaml)", "type": "PolicyNotConfigured"})
    dec = pol.evaluate_action(
        model_tier=arguments.get("model_tier"), estimated_cost=arguments.get("estimated_cost"),
        spent_so_far=arguments.get("spent_so_far"), operation=arguments.get("operation"),
        gates_passed=arguments.get("gates_passed", []))
    return json.dumps(dec.to_dict())


@tool(name="record_audit", description="Append a tamper-evident, hash-chained audit record of an AI-assisted change ('the trace'); returns the record and chain verification status",
         schema={"type": "object", "properties": {"task": {"type": "string"}, "agent": {"type": "string", "default": ""}, "model": {"type": "string", "default": ""}, "cost_usd": {"type": "number", "default": 0.0}, "rules_applied": {"type": "array", "items": {"type": "string"}, "default": []}, "gate_decision": {"type": "string", "default": ""}, "compliance_decision": {"type": "string", "default": ""}, "files_touched": {"type": "array", "items": {"type": "string"}, "default": []}}, "required": ["task"]})
async def _handle_record_audit(ctx: ServerContext, arguments: dict) -> str:
    audit = _get_audit_log()
    rec = audit.append(
        arguments.get("task", ""), agent=arguments.get("agent", ""), model=arguments.get("model", ""),
        cost_usd=float(arguments.get("cost_usd", 0.0)), rules_applied=arguments.get("rules_applied", []),
        gate_decision=arguments.get("gate_decision", ""), compliance_decision=arguments.get("compliance_decision", ""),
        files_touched=arguments.get("files_touched", []))
    ok, msg = audit.verify()
    return json.dumps({"record": rec.__dict__, "chain_ok": ok, "chain_msg": msg})


@tool(name="export_audit", description="Export the full AI-change audit trail (portable JSON + human-readable text) with hash-chain verification status",
         schema={"type": "object", "properties": {"format": {"type": "string", "enum": ["json", "text", "both"], "default": "both"}}})
async def _handle_export_audit(ctx: ServerContext, arguments: dict) -> str:
    audit = _get_audit_log()
    ok, msg = audit.verify()
    fmt = arguments.get("format", "both")
    out = {"chain_ok": ok, "chain_msg": msg, "record_count": len(audit.records)}
    if fmt in ("json", "both"):
        out["json"] = json.loads(audit.export_json())
    if fmt in ("text", "both"):
        out["text"] = audit.export_text()
    return json.dumps(out)


@tool(name="sync_agent_config", description="Compile one governance source (policy + packs + method) into every agent's native rules file (CLAUDE.md, AGENTS.md, .cursor/rules, copilot-instructions, .clinerules, GEMINI.md, .windsurfrules, .aiassistant/rules). Non-destructive: only the managed block is regenerated; user edits are preserved",
         schema={"type": "object", "properties": {"project": {"type": "string"}, "policy_summary": {"type": "array", "items": {"type": "string"}, "default": []}, "packs": {"type": "array", "items": {"type": "string"}, "default": []}, "rules": {"type": "array", "items": {"type": "string"}, "default": []}, "repo_root": {"type": "string", "default": "."}, "targets": {"type": "array", "items": {"type": "string"}}, "path_rules": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}, "description": "glob -> path-scoped rules (Copilot .github/instructions/*)"}, "mode": {"type": "string", "enum": ["apply", "preview", "check"], "default": "apply"}, "adopt": {"type": "boolean", "default": False}}, "required": ["project"]})
async def _handle_sync_agent_config(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.config_emitter import ConfigEmitter, GovernanceBundle
    bundle = GovernanceBundle.from_context(arguments)
    res = ConfigEmitter().sync(
        bundle, arguments.get("repo_root", "."), arguments.get("targets"),
        mode=arguments.get("mode", "apply"), adopt=arguments.get("adopt", False))
    return json.dumps({"written": res})


@tool(name="detect_agents", description="Detect which coding agents a repo is configured for (CLAUDE.md, AGENTS.md, .cursor/rules, copilot) + confidence + recommended targets",
         schema={"type": "object", "properties": {"repo_root": {"type": "string", "default": "."}}})
async def _handle_detect_agents(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.agent_detector import detect_agents
    d = detect_agents(arguments.get("repo_root", "."))
    return json.dumps({"targets": d.targets, "confidence": d.confidence, "fingerprints": d.fingerprints})


@tool(name="build_context_model", description="Derive structured intent/role/stack/domain/regulated context from a prompt (+ optional repo) to drive config emission",
         schema={"type": "object", "properties": {"text": {"type": "string"}, "repo_root": {"type": "string", "default": "."}}, "required": ["text"]})
async def _handle_build_context_model(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.context_model import build_context_model
    cm = build_context_model(arguments["text"], arguments.get("repo_root", "."))
    return json.dumps({"intent": cm.intent, "role": cm.role, "stack": cm.stack,
                       "domain": cm.domain, "regulated": cm.regulated})


@tool(name="propose_agent_config", description="Preview a unified diff of the agent rules files PromptWise would write, per target, WITHOUT writing — the review step before apply",
         schema={"type": "object", "properties": {"project": {"type": "string"}, "policy_summary": {"type": "array", "items": {"type": "string"}, "default": []}, "packs": {"type": "array", "items": {"type": "string"}, "default": []}, "rules": {"type": "array", "items": {"type": "string"}, "default": []}, "text": {"type": "string"}, "repo_root": {"type": "string", "default": "."}, "targets": {"type": "array", "items": {"type": "string"}}, "path_rules": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}}, "adopt": {"type": "boolean", "default": False}}, "required": ["project"]})
async def _handle_propose_agent_config(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.config_emitter import ConfigEmitter, GovernanceBundle
    from promptwise.core.agent_detector import detect_agents
    root = arguments.get("repo_root", ".")
    targets = arguments.get("targets") or detect_agents(root).targets
    bundle = GovernanceBundle.from_context(arguments)
    return json.dumps(ConfigEmitter().diff(bundle, root, targets, adopt=arguments.get("adopt", False)))


@tool(name="lint_agent_config", description="Lint an agent rules file (or content) for token tax, byte caps, missing .mdc frontmatter, and inferable bloat",
         schema={"type": "object", "properties": {"content": {"type": "string"}, "path": {"type": "string"}, "fmt": {"type": "string", "enum": ["md", "mdc"], "default": "md"}, "max_bytes": {"type": "integer"}, "always_apply": {"type": "boolean", "default": False}, "token_budget": {"type": "integer", "default": 0}}})
async def _handle_lint_agent_config(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.config_linter import ConfigLinter
    linter = ConfigLinter()
    kw = {"fmt": arguments.get("fmt", "md"), "max_bytes": arguments.get("max_bytes"),
          "always_apply": arguments.get("always_apply", False), "token_budget": arguments.get("token_budget", 0)}
    if arguments.get("path"):
        res = linter.lint_file(arguments["path"], **kw)
    else:
        res = linter.lint(arguments.get("content", ""), **kw)
    return json.dumps({"valid": res.valid,
                       "issues": [{"severity": i.severity, "message": i.message, "line": i.line} for i in res.issues]})


@tool(name="check_portability", description="Cross-host portability check (Phase 7 §7.4): verify the emitted governance configs for every supported host (CLAUDE.md, AGENTS.md, .cursor/rules, copilot, .clinerules, GEMINI.md, .windsurfrules, .aiassistant/rules) are present, well-formed, and in sync with the current skill/agent surface (skill_packs / agents / commands); reports drift precisely. Set emit_ci to also return a host-neutral CI-snippet that runs the governance gates using tiers/families only. Offline.",
         schema={"type": "object", "properties": {"repo_root": {"type": "string", "default": "."}, "hosts": {"type": "array", "items": {"type": "string"}, "description": "subset of supported hosts to check; default all"}, "emit_ci": {"type": "boolean", "default": False, "description": "also return a host-neutral CI-snippet"}}})
async def _handle_check_portability(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.portability_check import check_portability, emit_ci_snippet
    rep = check_portability(arguments.get("repo_root", "."), hosts=arguments.get("hosts"))
    out = rep.to_dict()
    if arguments.get("emit_ci", False):
        out["ci_snippet"] = emit_ci_snippet()
    return json.dumps(out)


@tool(name="export_web_bundle", description="Flatten one governance source (policy + packs + method) into a SINGLE self-contained, pasteable file for web-chat hosts with no IDE/CLI/MCP support (ChatGPT, Gemini, Claude.ai web chat). Not a managed-block IDE config: every call fully regenerates the bundle, there is no user-owned region to preserve. Set out_path to also write it to disk.",
         schema={"type": "object", "properties": {"project": {"type": "string"}, "policy_summary": {"type": "array", "items": {"type": "string"}, "default": []}, "packs": {"type": "array", "items": {"type": "string"}, "default": []}, "rules": {"type": "array", "items": {"type": "string"}, "default": []}, "text": {"type": "string"}, "skill_root": {"type": "string", "default": "skill_packs"}, "include_packs": {"type": "boolean", "default": True}, "out_path": {"type": "string", "description": "optional path to also write the bundle as a single file"}}, "required": ["project"]})
async def _handle_export_web_bundle(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.config_emitter import GovernanceBundle
    from promptwise.core.web_bundle import WebBundleEmitter
    bundle = GovernanceBundle.from_context(arguments)
    emitter = WebBundleEmitter()
    kw = {"skill_root": arguments.get("skill_root", "skill_packs"),
          "include_packs": arguments.get("include_packs", True)}
    out_path = arguments.get("out_path")
    if out_path:
        content = emitter.write(bundle, out_path, **kw)
        return json.dumps({"written": out_path, "bytes": len(content.encode("utf-8"))})
    content = emitter.render(bundle, **kw)
    return json.dumps({"bundle": content, "bytes": len(content.encode("utf-8"))})


# capture_learning/replay_learnings/learning_insights/insights_report
# (handlers.learning) originally sat right here, between
# export_web_bundle and tune_permissions -- register at this position to
# preserve tool registration order.
_add_handler_module("learning")


# tune_permissions/audit_mcp_servers/search_trace/rank_context
# (handlers.policy_intel) originally sat right here, between
# insights_report and optimize_skill_pack -- register at this position to
# preserve tool registration order.
_add_handler_module("policy_intel")


# optimize_skill_pack (handlers.skill_optimization) originally sat right
# here, between rank_context and export_compliance_bundle -- register it at
# this position to preserve tool registration order (golden snapshot).
_add_handler_module("skill_optimization")


# export_compliance_bundle (handlers.compliance_export) originally sat right
# here, between rank_context/optimize_skill_pack and export_org_report --
# register it at this position to preserve tool registration order.
_add_handler_module("compliance_export")


# export_org_report (handlers.scheduled_export) originally sat right here,
# between export_compliance_bundle and run_governor -- register it at this
# position to preserve tool registration order.
_add_handler_module("scheduled_export")


# run_governor/governor_undo (handlers.governor) originally sat right here,
# after export_org_report -- register at this position to preserve tool
# registration order.
_add_handler_module("governor")


async def call_tool(ctx: ServerContext, name: str, arguments: dict) -> str:
    try:
        handler = _HANDLERS.get(name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {name}", "type": "UnknownTool", "tool": name})
        result = await handler(ctx, arguments)
        from promptwise.core.response_budget import cap_response
        return cap_response(name, result)
    except Exception as e:
        return json.dumps({"error": str(e), "type": type(e).__name__, "tool": name})


async def main() -> None:
    # repo root = src/promptwise/server.py -> parents[2]; config/ and skills/ live there.
    config_dir = Path(__file__).resolve().parents[2]
    config = load_config(config_dir)

    db_path = await init_db()
    mm = MemoryManager(db_path)
    await mm.init()

    task_tracker = TaskTracker(db_path)
    await task_tracker.init()

    skills_dir = config_dir / config.skills.directory
    skill_loader = SkillLoader(skills_dir)
    skill_loader.load_skills()

    ctx = ServerContext(
        config=config,
        router=Router(config),
        rewriter=Rewriter(config),
        optimizer=Optimizer(config),
        compression=CompressionEngine(),
        cache_planner=CachePlanner(config),
        batcher=Batcher(config),
        summarizer=Summarizer(config),
        role_detector=RoleDetector(),
        orchestrator=Orchestrator(),
        quality=QualityGuard(),
        security=SecurityScanner(config.security),
        compliance=ComplianceEngine(config_dir / "config" / "compliance" if (config_dir / "config").exists() else None),
        code_validator=CodeValidator(),
        budget=BudgetGuardian(limit_usd=config.policies.budget_hard_stop_usd, team_budget_usd=config.policies.team_budget_usd, config=config),
        cost_monitor=CostMonitor(),
        roi=ROITracker(),
        session_manager=SessionManager(db_path),
        memory=mm,
        skill_loader=skill_loader,
        workflow_planner=WorkflowPlanner(),
        task_tracker=task_tracker,
    )

    server = Server("promptwise")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return await list_tools()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        result = await call_tool(ctx, name, arguments)
        return [TextContent(type="text", text=result)]

    from promptwise import __version__ as _pw_version
    init_opts = InitializationOptions(
        server_name="promptwise",
        server_version=_pw_version,
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, initialization_options=init_opts)


def sync_main() -> None:
    """Synchronous entry point for console_scripts."""
    asyncio.run(main())


# -- Backward-compat re-exports (15 existing test files reference
#    server._handle_* directly; each move task adds its handlers here) --
from promptwise.handlers.code_validation import _handle_validate_output  # noqa: F401
from promptwise.handlers.skill_optimization import _handle_optimize_skill_pack  # noqa: F401
from promptwise.handlers.compliance_export import _handle_export_compliance_bundle  # noqa: F401
from promptwise.handlers.scheduled_export import _handle_export_org_report  # noqa: F401
from promptwise.handlers.governor import _handle_run_governor, _handle_governor_undo  # noqa: F401
from promptwise.handlers.orchestration import _handle_orchestrate_tasks, _handle_run_autonomous  # noqa: F401
from promptwise.handlers.roi import _handle_track_roi, _handle_get_roi_report, _handle_cost_report  # noqa: F401
from promptwise.handlers.prompt_registry import _handle_save_prompt, _handle_search_prompts, _handle_compare_prompts  # noqa: F401
from promptwise.handlers.memory_session import _handle_get_memory_context, _handle_query_memory, _handle_ping_session, _handle_check_session_timeout  # noqa: F401
from promptwise.handlers.skills import _handle_invoke_skill, _handle_list_skills, _handle_skill_chain, _handle_suggest_skill  # noqa: F401
from promptwise.handlers.session_data import _handle_get_session_stats, _handle_clear_history, _handle_export_stats, _handle_reload_config  # noqa: F401
from promptwise.handlers.learning import _handle_capture_learning, _handle_replay_learnings, _handle_learning_insights, _handle_insights_report  # noqa: F401
from promptwise.handlers.policy_intel import _handle_tune_permissions, _handle_audit_mcp_servers, _handle_search_trace, _handle_rank_context  # noqa: F401
from promptwise.handlers.security import _handle_security_check, _handle_prompt_injection, _handle_owasp_scan, _handle_scan_response, _handle_benchmark_injection  # noqa: F401
from promptwise.handlers.budget_cost import _handle_monitor_budget, _handle_predict_cost, _handle_set_budget_limit, _handle_get_budget_status, _handle_budget_report  # noqa: F401
from promptwise.handlers.role_detection import _handle_plan_workflow, _handle_add_task, _handle_update_task, _handle_list_tasks, _handle_task_report, _handle_validate_mermaid, _handle_detect_role  # noqa: F401
from promptwise.handlers.prompt_engineering import _handle_suggest_technique, _handle_apply_craft, _handle_inject_few_shot, _handle_add_chain_of_thought, _handle_chain_prompts, _handle_eval_prompt_across_models, _handle_audit_system_prompt  # noqa: F401
from promptwise.handlers.energy_routing import _handle_check_energy, _handle_route_for_plugin, _handle_run_eval, _handle_run_eval_harness, _handle_get_sbom, _handle_run_security_suite, _handle_run_red_team_harness  # noqa: F401

_TOOL_DEFS = [entry.tool for entry in _registry.entries.values()]
_HANDLERS = {name: entry.handler for name, entry in _registry.entries.items()}

if __name__ == "__main__":
    asyncio.run(main())
