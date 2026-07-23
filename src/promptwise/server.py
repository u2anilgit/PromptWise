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


# ── Security ─────────────────────────────────────────────────────────
def _maybe_alert_security(result) -> None:
    """Best-effort, opt-in notification hook (Phase 16). Subscribes to an
    ALREADY-COMPUTED SecurityResult; never touches security/scanner.py."""
    try:
        from promptwise.core import alerts
        alerts.notify_security(result)
    except Exception:
        pass


def _maybe_alert_budget(status) -> None:
    """Best-effort, opt-in notification hook (Phase 16). Subscribes to an
    ALREADY-COMPUTED BudgetStatus; never touches plugins/budget.py."""
    try:
        from promptwise.core import alerts
        alerts.notify_budget(status)
    except Exception:
        pass


@tool(name="security_check", description="Run security check (secrets, injection, PII, destructive, permissions). Supply-chain OSV.dev lookups are off by default (air-gap safe); set allow_network=true to opt in.",
         schema={"type": "object", "properties": {"text": {"type": "string"}, "allow_network": {"type": "boolean", "default": False}}, "required": ["text"]})
async def _handle_security_check(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.security.check(arguments.get("text", ""), allow_network=bool(arguments.get("allow_network", False)))
    _maybe_alert_security(r)
    return json.dumps({"passed": r.passed, "risk_score": r.risk_score, "violations": r.violations, "blocked": r.blocked, "details": r.details})


@tool(name="prompt_injection", description="Scan user input for prompt injection or jailbreak attempts",
         schema={"type": "object", "properties": {"text": {"type": "string"}, "threshold": {"type": "number", "default": 0.7}}, "required": ["text"]})
async def _handle_prompt_injection(ctx: ServerContext, arguments: dict) -> str:
    text = arguments.get("text", "")
    threshold = float(arguments.get("threshold", 0.7))
    detected, confidence, found = ctx.security.detect_injection(text)
    action = "block" if confidence > threshold else ("warn" if confidence > 0 else "allow")
    return json.dumps({"injection_detected": detected, "confidence": round(confidence, 2), "patterns_found": found, "action": action})


@tool(name="owasp_scan", description="Scan code for OWASP Top-10 vulnerabilities",
         schema={"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string", "default": "python"}}, "required": ["code"]})
async def _handle_owasp_scan(ctx: ServerContext, arguments: dict) -> str:
    vulns = ctx.security.check_owasp(arguments.get("code", ""))
    weights = {"critical": 3, "high": 2, "medium": 1}
    risk = sum(weights.get(v["severity"], 1) for v in vulns)
    return json.dumps({"vulnerabilities": vulns, "risk_score": risk, "passed": risk < 4})


@tool(name="scan_response", description="Scan a model response for PII leaks, injection echoes, canary leaks, and responsible-AI signals (factual grounding vs. provided sources, bias/fairness, ethical disclosure). Pass a canary token (issued via the indirect-injection canary) to flag if content that flowed through tool output/RAG leaks back into the response. Advisory.",
         schema={"type": "object", "properties": {"response": {"type": "string"}, "original_prompt": {"type": "string", "default": ""}, "sources": {"type": "string", "default": "", "description": "Source/context text the response should be grounded in; enables grounding checks"}, "canary": {"type": "string", "default": "", "description": "Canary token placed in tool-output/RAG content; flags a leak if it reappears here"}}, "required": ["response"]})
async def _handle_scan_response(ctx: ServerContext, arguments: dict) -> str:
    response = arguments.get("response", "")
    original = arguments.get("original_prompt", "")
    pii_items, redacted = ctx.security.detect_pii(response, redact=True)
    inj_detected_orig, _, _ = ctx.security.detect_injection(original)
    inj_detected_resp, _, _ = ctx.security.detect_injection(response)
    echo = inj_detected_orig and inj_detected_resp
    leak = any(p in response.lower() for p in ["system prompt", "instructions say", "i was told to"])
    # Indirect-injection canary: if a canary planted in tool-output/RAG content
    # surfaces here, that content leaked back into the response.
    canary_leak = ctx.security.check_canary_leak(response, arguments.get("canary", ""))
    # Responsible-AI advisory: grounding / bias / ethics (heuristic, never blocks).
    try:
        from promptwise.core.responsible_ai import scan as _rai_scan
        rai = _rai_scan(response, sources=arguments.get("sources", ""))
    except Exception:
        rai = {"overall": "clean", "findings": []}
    return json.dumps({"pii_found": len(pii_items) > 0, "pii_items": pii_items, "injection_echo": echo,
                       "system_leak": leak, "canary_leak": canary_leak,
                       "safe": not pii_items and not echo and not leak and not canary_leak,
                       "redacted_response": redacted, "responsible_ai": rai})


@tool(name="benchmark_injection", description="Benchmark the prompt-injection detector against a bundled offline attack+benign corpus and report measured precision/recall/F1/accuracy plus the actual false positives/negatives (a real number, not a claim). Offline by default (air-gap safe); an optional live PINT-style corpus fetch is gated behind allow_network=true.",
         schema={"type": "object", "properties": {"threshold": {"type": "number", "default": 0.0}, "corpus_path": {"type": "string", "default": ""}, "pint_url": {"type": "string", "default": ""}, "allow_network": {"type": "boolean", "default": False}}})
async def _handle_benchmark_injection(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.security.injection_benchmark import benchmark_injection_detector
    report = benchmark_injection_detector(
        ctx.security,
        threshold=float(arguments.get("threshold", 0.0)),
        corpus_path=arguments.get("corpus_path") or None,
        pint_url=arguments.get("pint_url", ""),
        allow_network=bool(arguments.get("allow_network", False)),
    )
    return json.dumps(report.to_dict())


# ── Role Detection ───────────────────────────────────────────────────
@tool(name="plan_workflow", description="Classify a task (greenfield/brownfield/regulated) and return an ordered workflow of PromptWise's own skill packs + tools to run (PRD -> design -> stories -> TDD -> review). No third-party frameworks.",
         schema={"type": "object", "properties": {
             "text": {"type": "string"},
             "regulated": {"type": "boolean", "description": "Override auto-detection of regulated/compliance context"},
             "brownfield": {"type": "boolean", "description": "Override auto-detection of brownfield (existing-code) change"}},
         "required": ["text"]})
async def _handle_plan_workflow(ctx: ServerContext, arguments: dict) -> str:
    plan = ctx.workflow_planner.plan(
        text=arguments.get("text", ""),
        regulated=arguments.get("regulated"),
        brownfield=arguments.get("brownfield"))
    return json.dumps({"workflow": plan.workflow, "reason": plan.reason,
                       "steps": [{"phase": s.phase, "skill": s.skill, "kind": s.kind} for s in plan.steps],
                       "compliance_gate": plan.compliance_gate, "signals": plan.signals})


@tool(name="add_task", description="Create a development task with an effort estimate; tracks effort, tokens, and cost",
         schema={"type": "object", "properties": {
             "title": {"type": "string"},
             "estimate_hours": {"type": "number", "default": 0},
             "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"], "default": "todo"},
             "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["title"]})
async def _handle_add_task(ctx: ServerContext, arguments: dict) -> str:
    res = await ctx.task_tracker.add(
        title=arguments.get("title", ""), estimate_hours=arguments.get("estimate_hours", 0),
        status=arguments.get("status", "todo"), tags=arguments.get("tags"))
    return json.dumps(res)


@tool(name="update_task", description="Update a task's status, actual hours, tokens, or cost (set or increment)",
         schema={"type": "object", "properties": {
             "task_id": {"type": "string"},
             "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"]},
             "actual_hours": {"type": "number"}, "tokens": {"type": "number"}, "cost_usd": {"type": "number"},
             "add_tokens": {"type": "number"}, "add_cost": {"type": "number"}},
         "required": ["task_id"]})
async def _handle_update_task(ctx: ServerContext, arguments: dict) -> str:
    res = await ctx.task_tracker.update(
        task_id=arguments.get("task_id", ""), status=arguments.get("status"),
        actual_hours=arguments.get("actual_hours"), tokens=arguments.get("tokens"),
        cost_usd=arguments.get("cost_usd"), add_tokens=arguments.get("add_tokens"),
        add_cost=arguments.get("add_cost"))
    return json.dumps(res)


@tool(name="list_tasks", description="List tracked tasks, optionally filtered by status",
         schema={"type": "object", "properties": {
             "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"]}}})
async def _handle_list_tasks(ctx: ServerContext, arguments: dict) -> str:
    res = await ctx.task_tracker.list(status=arguments.get("status"))
    return json.dumps({"tasks": res, "count": len(res)})


@tool(name="task_report", description="Effort (estimate vs actual), token, and cost rollup across all tasks",
         schema={"type": "object", "properties": {}})
async def _handle_task_report(ctx: ServerContext, arguments: dict) -> str:
    return json.dumps(await ctx.task_tracker.report())


@tool(name="validate_mermaid", description="Lint Mermaid diagram source (type, bracket/quote balance) so it renders",
         schema={"type": "object", "properties": {"source": {"type": "string"}}, "required": ["source"]})
async def _handle_validate_mermaid(ctx: ServerContext, arguments: dict) -> str:
    r = validate_mermaid(arguments.get("source", ""))
    return json.dumps({"valid": r.valid, "diagram_type": r.diagram_type,
                       "errors": r.errors, "warnings": r.warnings, "node_count": r.node_count})


@tool(name="detect_role", description="Detect organizational role from prompt context",
         schema={"type": "object", "properties": {"text": {"type": "string"}, "file_type": {"type": "string"}}, "required": ["text"]})
async def _handle_detect_role(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.role_detector.detect(arguments.get("text", ""), context={"file_type": arguments.get("file_type", "")})
    return json.dumps({"role": r.primary_role, "confidence": r.confidence, "keywords_matched": r.keywords_matched,
                       "secondary_roles": [{"role": s, "confidence": c} for s, c in r.secondary_roles], "rationale": r.rationale})


# orchestrate_tasks/run_autonomous (handlers.orchestration) originally sat
# right here, between Role Detection and Budget & Cost -- register at this
# position to preserve tool registration order.
_add_handler_module("orchestration")


# ── Budget & Cost ────────────────────────────────────────────────────
@tool(name="monitor_budget", description="Check spend against budget limit",
         schema={"type": "object", "properties": {
             "used_usd": {"type": "number"}, "days_elapsed": {"type": "integer", "default": 1}, "project_id": {"type": "string"},
             "tool_cost_usd": {"type": "number", "description": "Tool/API execution cost for this workflow, attributed alongside used_usd's LLM token cost"}},
         "required": ["used_usd"]})
async def _handle_monitor_budget(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.budget.check(used_usd=float(arguments.get("used_usd", 0)), days_elapsed=int(arguments.get("days_elapsed", 1)),
                         project_id=arguments.get("project_id"), tool_cost_usd=float(arguments.get("tool_cost_usd", 0) or 0))
    _maybe_alert_budget(r)
    return json.dumps({"used_usd": r.used_usd, "limit_usd": r.limit_usd, "pct_used": r.pct_used,
                       "daily_burn_usd": r.daily_burn_usd, "projected_monthly_usd": r.projected_monthly_usd,
                       "alert_level": r.alert_level, "project_id": r.project_id, "cost_breakdown": r.cost_breakdown})


@tool(name="predict_cost", description="Estimate cost of a prompt before sending",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "model": {"type": "string", "default": "claude-sonnet-4-6"}}, "required": ["prompt"]})
async def _handle_predict_cost(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.budget.predict_cost(arguments.get("prompt", ""), model=arguments.get("model", "claude-sonnet-4-6"))
    return json.dumps(r)


@tool(name="set_budget_limit", description="Set monthly or daily spending limit",
         schema={"type": "object", "properties": {"limit_usd": {"type": "number"}, "period": {"type": "string", "enum": ["daily", "monthly"], "default": "monthly"}}, "required": ["limit_usd"]})
async def _handle_set_budget_limit(ctx: ServerContext, arguments: dict) -> str:
    ctx.budget.set_limit(float(arguments.get("limit_usd", 0)), period=arguments.get("period", "monthly"))
    return json.dumps({"status": "ok", "limit_usd": arguments.get("limit_usd"), "period": arguments.get("period", "monthly")})


@tool(name="get_budget_status", description="Check current spend vs configured budget limits",
         schema={"type": "object", "properties": {}})
async def _handle_get_budget_status(ctx: ServerContext, arguments: dict) -> str:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    logs = await ctx.memory.raw_cost_logs(since=month_start)
    current_spend = round(sum(float(row.get("cost_usd", 0) or 0) for row in logs), 6)
    days_elapsed = max(1, now.day)
    daily_burn = round(current_spend / days_elapsed, 6)
    return json.dumps(ctx.budget.get_budget_status(current_spend_usd=current_spend, daily_burn_usd=daily_burn))


@tool(name="budget_report", description="Get detailed budget report with cost anomaly detection",
         schema={"type": "object", "properties": {"period": {"type": "string", "enum": ["daily", "weekly", "monthly"], "default": "weekly"}, "project_id": {"type": "string"}}})
async def _handle_budget_report(ctx: ServerContext, arguments: dict) -> str:
    period = arguments.get("period", "weekly")
    window_days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    logs = await ctx.memory.raw_cost_logs(since=since)
    by_day: dict[str, float] = {}
    for row in logs:
        day = row["ts"][:10]
        by_day[day] = by_day.get(day, 0.0) + row["cost_usd"]
    daily_costs = [round(v, 6) for _, v in sorted(by_day.items())]
    anomaly = ctx.budget.cost_anomaly_detect(daily_costs)
    return json.dumps({"period": period, "project_id": arguments.get("project_id"),
                       "total_cost_usd": round(sum(daily_costs), 6), "anomaly": anomaly})


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


# ── Skills ───────────────────────────────────────────────────────────
@tool(name="invoke_skill", description="Invoke a specific skill with context",
         schema={"type": "object", "properties": {"skill_name": {"type": "string"}, "context": {"type": "object", "default": {}}, "params": {"type": "object", "default": {}}}, "required": ["skill_name"]})
async def _handle_invoke_skill(ctx: ServerContext, arguments: dict) -> str:
    sk = ctx.skill_loader.get_skill(arguments.get("skill_name", ""))
    if not sk:
        return json.dumps({"error": "Skill not found", "skill_name": arguments.get("skill_name")})
    res = await ctx.orchestrator.execute_skill(sk, arguments.get("context", {}), router=ctx.router)
    await _record_skill_execution(ctx, tool="invoke_skill", skill_name=sk.name, result=res)
    return json.dumps(res)


@tool(name="list_skills", description="List all available skills filtered by role",
         schema={"type": "object", "properties": {"role": {"type": "string"}, "category": {"type": "string"}}})
async def _handle_list_skills(ctx: ServerContext, arguments: dict) -> str:
    skills_list = []
    for sk in ctx.skill_loader.skills.values():
        role_filter = arguments.get("role")
        if role_filter and sk.roles and role_filter not in sk.roles:
            continue
        skills_list.append({"name": sk.name, "description": sk.description, "triggers": sk.triggers,
                            "depends_on": sk.depends_on, "roles": sk.roles, "model_tier": sk.model_tier})
    return json.dumps({"skills": skills_list})


@tool(name="skill_chain", description="Execute a list of skills sequentially",
         schema={"type": "object", "properties": {"skills": {"type": "array", "items": {"type": "string"}}, "mode": {"type": "string", "enum": ["sequential", "parallel"], "default": "sequential"}, "context": {"type": "object", "default": {}}}, "required": ["skills"]})
async def _handle_skill_chain(ctx: ServerContext, arguments: dict) -> str:
    res = await ctx.orchestrator.execute_skill_chain(ctx.skill_loader, arguments.get("skills", []),
                                                      arguments.get("mode", "sequential"), arguments.get("context", {}), router=ctx.router)
    for skill_name, skill_result in (res.get("results") or {}).items():
        await _record_skill_execution(ctx, tool="skill_chain", skill_name=skill_name, result=skill_result)
    return json.dumps(res)


@tool(name="suggest_skill", description="Recommend best skill for a given user message",
         schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
async def _handle_suggest_skill(ctx: ServerContext, arguments: dict) -> str:
    text = arguments.get("text", "")
    match = ctx.skill_loader.match_skill(text)
    if match:
        return json.dumps({"skill": match.name, "description": match.description})
    scored = sorted([{"name": sk.name, "score": sum(1 for t in sk.triggers if t.lower() in text.lower()) / max(len(sk.triggers), 1),
                      "description": sk.description} for sk in ctx.skill_loader.skills.values()], key=lambda x: x["score"], reverse=True)[:3]
    return json.dumps({"top_matches": scored, "note": "No high-confidence match"})


# ── Prompt Engineering ───────────────────────────────────────────────
@tool(name="suggest_technique", description="Auto-detect best prompting technique: CRAFT, Few-Shot, Chain-of-Thought, or Chaining",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]})
async def _handle_suggest_technique(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    pl = prompt.lower()
    if "example" in pl:
        tech, conf, reason = "Few-Shot", 0.85, "Prompt contains 'example'"
    elif any(kw in pl for kw in ("step", "reason", "explain why")):
        tech, conf, reason = "Chain-of-Thought", 0.85, "Prompt requests step-wise reasoning"
    elif len(prompt) > 200 and len(prompt.split(".")) > 3:
        tech, conf, reason = "Chaining", 0.75, "Complex multi-sentence task"
    else:
        tech, conf, reason = "CRAFT", 0.80, "Short prompt; add Context/Role/Action/Format/Tone"
    return json.dumps({"technique": tech, "confidence": conf, "rationale": reason})


@tool(name="apply_craft", description="Analyze prompt against CRAFT axes (Context/Role/Action/Format/Tone) and rebuild",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]})
async def _handle_apply_craft(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    pl = prompt.lower()
    axes = {"context": any(kw in pl for kw in ["context", "background", "given"]),
            "role": any(kw in pl for kw in ["you are", "act as", "as a"]),
            "action": any(kw in pl for kw in ["write", "generate", "analyze", "summarize", "create", "explain"]),
            "format": any(kw in pl for kw in ["format", "bullet", "markdown", "json", "table"]),
            "tone": any(kw in pl for kw in ["tone", "formal", "casual", "professional"])}
    score = sum(20 for v in axes.values() if v)
    missing = [ax for ax, v in axes.items() if not v]
    adds = []
    if not axes["context"]: adds.append("Context: [Describe background]")
    if not axes["role"]: adds.append("Role: You are a helpful expert assistant.")
    if not axes["format"]: adds.append("Format: Respond in clear, structured paragraphs.")
    if not axes["tone"]: adds.append("Tone: Professional and concise.")
    improved = "\n".join(adds) + ("\n\n" if adds else "") + prompt
    return json.dumps({"axes": axes, "score": score, "missing_axes": missing, "improved_prompt": improved})


@tool(name="inject_few_shot", description="Enhance prompt with few-shot examples",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "examples": {"type": "array", "items": {"type": "object"}, "default": []}}, "required": ["prompt"]})
async def _handle_inject_few_shot(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    examples = arguments.get("examples", [])
    if examples:
        formatted = "\n".join(f"Example {i+1}:\nInput: {ex.get('input', '')}\nOutput: {ex.get('output', '')}" for i, ex in enumerate(examples))
        enhanced = formatted + "\n\n" + prompt
        return json.dumps({"enhanced_prompt": enhanced, "example_count": len(examples)})
    return json.dumps({"enhanced_prompt": "[INSERT EXAMPLES HERE]\n\n" + prompt, "example_count": 0})


@tool(name="add_chain_of_thought", description="Wrap prompt with Chain-of-Thought scaffold",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "style": {"type": "string", "enum": ["standard", "step-by-step", "tree-of-thought"], "default": "step-by-step"}}, "required": ["prompt"]})
async def _handle_add_chain_of_thought(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    style = arguments.get("style", "step-by-step")
    cot = {"standard": "Think step by step.", "tree-of-thought": "Consider multiple approaches before answering.",
           "step-by-step": "Let's approach this step by step:\n1. First, understand the problem.\n2. Then, work through each part.\n3. Finally, synthesize the answer."}.get(style, "Think step by step.")
    return json.dumps({"wrapped_prompt": prompt + "\n\n" + cot, "technique_applied": style})


@tool(name="chain_prompts", description="Decompose complex task into sequential prompt chain",
         schema={"type": "object", "properties": {"task": {"type": "string"}, "steps": {"type": "integer", "default": 3}}, "required": ["task"]})
async def _handle_chain_prompts(ctx: ServerContext, arguments: dict) -> str:
    task = arguments.get("task", "")
    steps = int(arguments.get("steps", 3))
    sents = [s.strip() for s in task.split(".") if s.strip()]
    chain = [{"step": i+1, "prompt": f"Step {i+1}: {(sents[i] if i < len(sents) else f'Continue step {i+1}')}.",
              "input_from": f"step_{i}" if i > 0 else "user", "output_to": f"step_{i+2}" if i < steps-1 else "final_output"} for i in range(steps)]
    return json.dumps({"chain": chain, "handoff_instructions": "Pass output of each step as input to the next."})


@tool(name="eval_prompt_across_models", description="Estimate cost and recommend model tier across Haiku/Sonnet/Opus",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "task_type": {"type": "string", "default": "general"}}, "required": ["prompt"]})
async def _handle_eval_prompt_across_models(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    inp = max(1, len(prompt) // 4)
    out = inp * 2
    tiers = {"haiku": {"cost_usd": round(inp*0.0000008+out*0.000004, 8), "quality": "good for simple tasks"},
             "sonnet": {"cost_usd": round(inp*0.000003+out*0.000015, 8), "quality": "best balance"},
             "opus": {"cost_usd": round(inp*0.000015+out*0.000075, 8), "quality": "highest quality"}}
    rec, reason = ("haiku", "Short prompt") if inp < 200 else ("sonnet", "Medium complexity") if inp < 1000 else ("opus", "Long/complex")
    return json.dumps({"recommendation": rec, "tiers": tiers, "rationale": reason, "estimated_input_tokens": inp})


@tool(name="audit_system_prompt", description="Score system prompt on clarity, role, constraints, and jailbreak resistance",
         schema={"type": "object", "properties": {"system_prompt": {"type": "string"}}, "required": ["system_prompt"]})
async def _handle_audit_system_prompt(ctx: ServerContext, arguments: dict) -> str:
    sp = arguments.get("system_prompt", "")
    spl = sp.lower()
    issues = []
    score = 0
    if any(kw in spl for kw in ("you are", "act as", "your role")):
        score += 20
    else:
        issues.append("Missing role definition")
    if any(kw in spl for kw in ("do not", "never", "must not", "avoid")):
        score += 20
    else:
        issues.append("Missing constraints")
    if any(kw in spl for kw in ("format", "output", "respond in")):
        score += 20
    else:
        issues.append("Missing output format")
    if not any(p in spl for p in ["ignore previous", "disregard", "override"]):
        score += 20
    else:
        issues.append("Injection pattern detected")
    if len(sp) > 50:
        score += 20
    else:
        issues.append("Too short, unclear task")
    adds = []
    if "Missing role" in " ".join(issues):
        adds.append("You are a helpful, knowledgeable assistant.")
    if "Missing constraints" in " ".join(issues):
        adds.append("Do not discuss topics outside your defined scope.")
    if "Missing output format" in " ".join(issues):
        adds.append("Respond in clear, structured paragraphs.")
    return json.dumps({"score": score, "issues": issues, "improved_prompt": "\n".join(adds) + ("\n\n" if adds else "") + sp})


# save_prompt/search_prompts/compare_prompts (handlers.prompt_registry)
# originally sat right here, between audit_system_prompt and
# get_session_stats -- register at this position to preserve tool
# registration order.
_add_handler_module("prompt_registry")


# ── Session Data ─────────────────────────────────────────────────────
@tool(name="get_session_stats", description="Get session usage statistics",
         schema={"type": "object", "properties": {"since": {"type": "string", "description": "ISO 8601 timestamp filter"}}})
async def _handle_get_session_stats(ctx: ServerContext, arguments: dict) -> str:
    snap = await ctx.memory.snapshot(since=arguments.get("since"))
    pricing_age = getattr(ctx.config, "last_verified", None)
    return json.dumps({**snap, "pricing_last_verified": pricing_age})


@tool(name="clear_history", description="Delete usage history older than N days",
         schema={"type": "object", "properties": {"older_than_days": {"type": "integer", "minimum": 1}}, "required": ["older_than_days"]})
async def _handle_clear_history(ctx: ServerContext, arguments: dict) -> str:
    deleted = await ctx.memory.clear_old(older_than_days=int(arguments.get("older_than_days", 90)))
    return json.dumps({"deleted_count": deleted, "older_than_days": arguments.get("older_than_days", 90)})


@tool(name="export_stats", description="Export usage history as JSON",
         schema={"type": "object", "properties": {"since": {"type": "string"}, "format": {"type": "string", "enum": ["json", "csv"], "default": "json"}}})
async def _handle_export_stats(ctx: ServerContext, arguments: dict) -> str:
    raw = await ctx.memory.export_json(since=arguments.get("since"))
    if arguments.get("format", "json") != "csv":
        return raw
    import csv
    import io
    entries = json.loads(raw)
    buf = io.StringIO()
    fieldnames = ["entry_id", "session_id", "ts", "tool", "summary", "cost_usd", "tags"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for e in entries:
        writer.writerow({**e, "tags": json.dumps(e["tags"])})
    return buf.getvalue()


@tool(name="reload_config", description="Reload configuration without restarting server",
         schema={"type": "object", "properties": {}})
async def _handle_reload_config(ctx: ServerContext, arguments: dict) -> str:
    ctx.config = load_config()
    return json.dumps({"reloaded": True})


# ── Energy & Plugin Routing ──────────────────────────────────────────
@tool(name="check_energy", description="Get energy efficiency score for a model",
         schema={"type": "object", "properties": {"model": {"type": "string"}, "tokens": {"type": "integer", "default": 1000}}, "required": ["model"]})
async def _handle_check_energy(ctx: ServerContext, arguments: dict) -> str:
    score = ctx.cost_monitor.energy_efficiency_score(arguments.get("model", ""), int(arguments.get("tokens", 1000)))
    return json.dumps({"energy_efficiency_score": score, "model": arguments.get("model")})


@tool(name="route_for_plugin", description="Detect applicable plugin for text",
         schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
async def _handle_route_for_plugin(ctx: ServerContext, arguments: dict) -> str:
    plugin = ctx.router.route_for_plugin(arguments.get("text", ""))
    return json.dumps({"plugin": plugin})


@tool(name="run_eval", description="Estimate and compare per-model cost for a prompt across multiple models (cost only -- for a real quality comparison, use run_eval_harness)",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "models": {"type": "array", "items": {"type": "string"}, "default": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"]}}, "required": ["prompt"]})
async def _handle_run_eval(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    default_models = ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"]
    scores = {m: ctx.budget.predict_cost(prompt, model=m) for m in arguments.get("models", default_models)}
    return json.dumps({"prompt": prompt, "eval": scores})


@tool(name="run_eval_harness", description="Run a durable eval + regression suite (prompt+rubric cases) offline; score with the quality gate, diff against a stored baseline to flag regressions, expose a pass/fail gate, and feed outcomes back into adaptive routing. Offline default is a record/dry-run mode (no cloud). Set save_baseline=true to bless this run as the new baseline.",
         schema={"type": "object", "properties": {"cases": {"type": "array", "items": {"type": "object"}, "default": []}, "cases_path": {"type": "string", "default": ""}, "suite": {"type": "string", "default": "default"}, "tiers": {"type": "array", "items": {"type": "string"}}, "bar": {"type": "number", "default": 0.6}, "save_baseline": {"type": "boolean", "default": False}}})
async def _handle_run_eval_harness(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.adaptive_router import OutcomeStore
    from promptwise.core.eval_harness import (
        EvalCase, EvalHarness, EvalResultStore, load_cases)
    cases = [EvalCase.from_dict(c) for c in arguments.get("cases", []) if isinstance(c, dict)]
    cases_path = arguments.get("cases_path", "")
    if cases_path:
        cases.extend(load_cases(cases_path))
    suite = arguments.get("suite", "default")
    harness = EvalHarness(
        runner=None,  # offline default: record/dry-run, never cloud
        outcome_store=OutcomeStore(), result_store=EvalResultStore(),
        bar=float(arguments.get("bar", 0.6)), suite=suite)
    run = harness.run(cases, tiers=arguments.get("tiers"))
    out = run.to_dict()
    if arguments.get("save_baseline"):
        out["baseline_saved"] = harness.save_baseline(run)
    return json.dumps(out)


@tool(name="get_sbom", description="Generate SBOM in CycloneDX format",
         schema={"type": "object", "properties": {"format": {"type": "string", "enum": ["cyclonedx", "spdx"], "default": "cyclonedx"}, "paths": {"type": "array", "items": {"type": "string"}}}})
async def _handle_get_sbom(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.sbom import SBOMGenerator
    gen = SBOMGenerator()
    sbom = gen.generate(arguments.get("paths", [Path.cwd()])[0] if arguments.get("paths") else Path.cwd())
    return json.dumps(sbom)


@tool(name="run_security_suite", description="Run all security checks as a suite",
         schema={"type": "object", "properties": {"targets": {"type": "array", "items": {"type": "string"}}, "context": {"type": "object"}}})
async def _handle_run_security_suite(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.security_log import SecurityScanStore
    text = " ".join(arguments.get("targets", []))
    sec = ctx.security.check(text)
    owasp = ctx.security.check_owasp(text)
    inj_detected, inj_confidence, inj_patterns = ctx.security.detect_injection(text)
    pii_items, _ = ctx.security.detect_pii(text)
    # sec.violations (from check()) already carries the injection and PII
    # findings reported below -- don't count them a second time here.
    findings_count = len(sec.violations) + len(owasp)
    severity_breakdown = {
        "critical": sum(1 for v in owasp if v["severity"] == "critical"),
        "high": sum(1 for v in owasp if v["severity"] == "high"),
        "medium": sum(1 for v in owasp if v["severity"] == "medium"),
    }
    try:
        SecurityScanStore().record(
            checks_run=list(sec.checks_run), findings_count=findings_count,
            severity_breakdown=severity_breakdown, passed=sec.passed and not owasp)
    except Exception:
        pass  # storage is best-effort; a full disk must not sink the suite
    _maybe_alert_security(sec)
    return json.dumps({"security": {"passed": sec.passed, "violations": sec.violations, "risk_score": sec.risk_score},
                       "owasp": owasp,
                       "injection": {"detected": inj_detected, "confidence": round(inj_confidence, 2), "patterns_found": inj_patterns},
                       "pii": {"found": len(pii_items) > 0, "items": pii_items},
                       "status": "completed"})


@tool(name="run_red_team_harness", description="Run a durable, offline red-team suite against the security scanners: known attack patterns (must be caught) and benign counterexamples (must NOT be flagged) across injection/owasp/secrets/destructive/permissions/pii/supply_chain checks. Diffs against a stored baseline to flag regressions (an attack that used to be caught now escapes, or a benign input starts false-positiving) and exposes a pass/fail gate. Defaults to a built-in corpus when no cases/cases_path given. Set save_baseline=true to bless this run as the new baseline.",
         schema={"type": "object", "properties": {"cases": {"type": "array", "items": {"type": "object"}, "default": []}, "cases_path": {"type": "string", "default": ""}, "suite": {"type": "string", "default": "default"}, "save_baseline": {"type": "boolean", "default": False}}})
async def _handle_run_red_team_harness(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.redteam_harness import (
        RedTeamCase, RedTeamHarness, RedTeamResultStore, builtin_cases, load_cases)
    cases = [RedTeamCase.from_dict(c) for c in arguments.get("cases", []) if isinstance(c, dict)]
    cases_path = arguments.get("cases_path", "")
    if cases_path:
        cases.extend(load_cases(cases_path))
    if not cases and not cases_path:
        cases = builtin_cases()
    suite = arguments.get("suite", "default")
    harness = RedTeamHarness(result_store=RedTeamResultStore(), suite=suite)
    run = harness.run(cases)
    out = run.to_dict()
    if arguments.get("save_baseline"):
        out["baseline_saved"] = harness.save_baseline(run)
    return json.dumps(out)


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


# ── Continuous learning loop (Phase 2) ───────────────────────────────
@tool(name="capture_learning", description="Store a correction as a durable, searchable learning (category, mistake, fix, project). Local SQLite + FTS5, offline.",
         schema={"type": "object", "properties": {
             "category": {"type": "string", "description": "e.g. 'style', 'security', 'api-misuse'"},
             "mistake": {"type": "string", "description": "what went wrong"},
             "correction": {"type": "string", "description": "the fix / the rule going forward"},
             "project": {"type": "string", "default": ""},
             "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["category", "mistake", "correction"]})
async def _handle_capture_learning(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.learning_store import LearningStore
    learning = LearningStore().capture(
        category=arguments.get("category", ""), mistake=arguments.get("mistake", ""),
        correction=arguments.get("correction", ""), project=arguments.get("project", ""),
        tags=arguments.get("tags", []))
    return json.dumps({"captured": learning.to_dict()})


@tool(name="replay_learnings", description="Top-K relevant past corrections for a task description (FTS5 BM25, LIKE fallback) plus a ready-to-inject reminder block.",
         schema={"type": "object", "properties": {
             "task": {"type": "string"}, "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 25},
             "project": {"type": "string"}},
         "required": ["task"]})
async def _handle_replay_learnings(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.learning_replay import replay
    return json.dumps(replay(arguments.get("task", ""), k=arguments.get("k", 5),
                             project=arguments.get("project")))


@tool(name="learning_insights", description="Correction trends from the local learning store: counts by category, project, month, and the most-repeated mistakes.",
         schema={"type": "object", "properties": {}})
async def _handle_learning_insights(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.insights import compute_insights
    return json.dumps(compute_insights())


@tool(name="insights_report", description="Ranked, actionable recommendations over local telemetry: routing downgrades/escalations, top cost drivers & spend anomalies, quality/eval regressions, and budget projections. Deterministic, offline, min-sample gated.",
         schema={"type": "object", "properties": {
             "window_days": {"type": "integer", "default": 30, "minimum": 1, "maximum": 365,
                             "description": "analysis window for cost/quality/budget families"},
             "top_n": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100}}})
async def _handle_insights_report(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.insights import compute_recommendations
    recs = compute_recommendations(window_days=arguments.get("window_days", 30))
    top_n = int(arguments.get("top_n", 10))
    return json.dumps({"count": len(recs), "recommendations": recs[:top_n]})


# ── Policy intelligence & searchable trace (Phase 4) ─────────────────
@tool(name="tune_permissions", description="Learn allow/deny permission suggestions from denial telemetry (the Phase 1 PermissionDenied log). Proposals only — never edits config.",
         schema={"type": "object", "properties": {
             "state_dir": {"type": "string", "default": ".", "description": "project dir holding .promptwise/denials.jsonl"},
             "min_count": {"type": "integer", "default": 2, "minimum": 1},
             "mcp_json": {"type": "string", "description": "path to .mcp.json for the current allowlist"}}})
async def _handle_tune_permissions(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.permission_tuner import tune_permissions
    return json.dumps(tune_permissions(
        state_dir=arguments.get("state_dir", "."),
        min_count=arguments.get("min_count", 2),
        mcp_json=arguments.get("mcp_json")))


@tool(name="audit_mcp_servers", description="Audit declared MCP servers (.mcp.json + plugin.json) for security flags, allow-surface, and redundancy. Offline; inspects config, does not call servers.",
         schema={"type": "object", "properties": {
             "repo_root": {"type": "string", "default": "."},
             "extra_configs": {"type": "array", "items": {"type": "string"}}}})
async def _handle_audit_mcp_servers(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.mcp_auditor import audit_mcp_servers
    return json.dumps(audit_mcp_servers(
        repo_root=arguments.get("repo_root", "."),
        extra_configs=arguments.get("extra_configs")))


@tool(name="search_trace", description="Search the trace (hash-chained audit trail + learnings) by meaning. Keyword/FTS by default; optional local embeddings if installed and enabled. Offline.",
         schema={"type": "object", "properties": {
             "query": {"type": "string"}, "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 25},
             "repo_root": {"type": "string", "default": "."},
             "audit_path": {"type": "string"},
             "use_embeddings": {"type": "boolean", "default": False}},
         "required": ["query"]})
async def _handle_search_trace(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.semantic_index import search_trace
    return json.dumps(search_trace(
        arguments.get("query", ""), k=arguments.get("k", 5),
        repo_root=arguments.get("repo_root", "."),
        audit_path=arguments.get("audit_path"),
        use_embeddings=arguments.get("use_embeddings", False)))


@tool(name="rank_context", description="Retrieval-augmented context manager: rank and prune candidates from the trace (audit + learnings) and an optionally-supplied doc onto one token budget. No new ranking algorithm - reuses search_trace's keyword/BM25 (or optional embeddings) scoring; docs are sharded per call, not indexed. Offline.",
         schema={"type": "object", "properties": {
             "query": {"type": "string"},
             "token_budget": {"type": "integer", "default": 2000},
             "doc_path": {"type": "string"},
             "doc_text": {"type": "string"},
             "sources": {"type": "array", "items": {"type": "string", "enum": ["audit", "learnings", "doc"]},
                        "default": ["audit", "learnings", "doc"]},
             "use_embeddings": {"type": "boolean", "default": False},
             "repo_root": {"type": "string", "default": "."},
             "audit_path": {"type": "string"},
             "learning_db": {"type": "string"}},
         "required": ["query"]})
async def _handle_rank_context(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.context_ranker import rank_context
    sources = arguments.get("sources") or ["audit", "learnings", "doc"]
    return json.dumps(rank_context(
        arguments.get("query", ""), token_budget=arguments.get("token_budget", 2000),
        doc_path=arguments.get("doc_path"), doc_text=arguments.get("doc_text"),
        sources=tuple(sources), use_embeddings=arguments.get("use_embeddings", False),
        repo_root=arguments.get("repo_root", "."), audit_path=arguments.get("audit_path"),
        learning_db=arguments.get("learning_db")))


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

_TOOL_DEFS = [entry.tool for entry in _registry.entries.values()]
_HANDLERS = {name: entry.handler for name, entry in _registry.entries.items()}

if __name__ == "__main__":
    asyncio.run(main())
