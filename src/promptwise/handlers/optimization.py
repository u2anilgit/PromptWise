"""handlers.optimization -- routing, prompt-optimization, and caching MCP
tool handlers (moved verbatim from server.py's unsectioned preamble block
during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.session_context import CURRENT_SESSION_ID
from promptwise.core.tool_registry import ServerContext, tool, _resolve_effort


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
    await ctx.memory.record_cost(tool="route_request", session_id=CURRENT_SESSION_ID, model=r.recommended_model, cost_usd=r.estimated_input_cost_usd)
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
    await ctx.memory.record_cost(tool="rewrite_prompt", session_id=CURRENT_SESSION_ID, model=arguments.get("model", "claude-sonnet-4-6"), input_tokens=r.raw_tokens, saving_pct=r.saving_pct)
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


@tool(name="compare_providers", description="Advisory cost comparison for the same estimated token count: the claude entry uses this project's live registry pricing (the real source of truth); non-claude entries (OpenAI/Gemini/etc, when include_external=true, the default) come from a static, offline, user-editable reference catalog (config/external_models.yaml) -- never live-fetched, never consulted by routing, purely informational. Each result is tagged advisory:true/false so callers never mistake a reference price for a live one.",
         schema={"type": "object", "properties": {
             "text": {"type": "string"}, "model": {"type": "string", "default": "claude-sonnet-4-6"},
             "include_external": {"type": "boolean", "default": True}},
         "required": ["text"]})
async def _handle_compare_providers(ctx: ServerContext, arguments: dict) -> str:
    comparisons = ctx.router.compare_providers(
        arguments.get("text", ""), model=arguments.get("model", "claude-sonnet-4-6"),
        include_external=bool(arguments.get("include_external", True)))
    return json.dumps({"comparisons": comparisons})
