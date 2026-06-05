"""MCP server for PromptWise."""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path = [p for p in sys.path if p not in ("", str(Path.cwd()))]

from promptwise.batcher import Batcher
from promptwise.cache_planner import CachePlanner
from promptwise.compactor import Compactor
from promptwise.config import AppConfig, load_config
from promptwise.db import init_db
from promptwise.optimizer import Optimizer
from promptwise.rewriter import Rewriter
from promptwise.router import Router
from promptwise.session_manager import SessionManager
from promptwise.stats import StatsService
from promptwise.summarizer import Summarizer


@dataclass
class ServerContext:
    """Dependency injection container."""

    config: AppConfig
    rewriter: Rewriter
    optimizer: Optimizer
    router: Router
    cache_planner: CachePlanner
    batcher: Batcher
    summarizer: Summarizer
    stats: StatsService
    session_manager: SessionManager
    compactor: Compactor


async def list_tools(ctx: ServerContext = None) -> list[Tool]:
    """List available tools (module-level for testing)."""
    return [
        Tool(
            name="rewrite_prompt",
            description="Rewrite prompt with role framing and filler removal",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The prompt to rewrite",
                    },
                    "role": {
                        "type": "string",
                        "enum": [
                            "general",
                            "developer",
                            "analyst",
                            "writer",
                            "manager",
                            "researcher",
                            "designer",
                        ],
                        "default": "general",
                    },
                    "model": {
                        "type": "string",
                        "default": "claude-sonnet-4-6",
                        "description": "Model for token counting",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="optimize_context",
            description="Compress context to fit token budget",
            inputSchema={
                "type": "object",
                "properties": {
                    "context": {"type": "string"},
                    "token_budget": {
                        "type": "integer",
                        "default": 2000,
                        "minimum": 100,
                    },
                    "model": {
                        "type": "string",
                        "default": "claude-sonnet-4-6",
                    },
                },
                "required": ["context"],
            },
        ),
        Tool(
            name="route_request",
            description="Route request to appropriate model",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "intent": {
                        "type": "string",
                        "enum": [
                            "auto",
                            "extract",
                            "classify",
                            "summarize",
                            "question",
                            "code",
                            "analysis",
                            "agent_loop",
                            "research",
                        ],
                        "default": "auto",
                    },
                    "stakes": {
                        "type": "string",
                        "enum": ["auto", "low", "medium", "high"],
                        "default": "auto",
                    },
                    "provider": {"type": "string", "default": "claude"},
                    "monthly_budget_usd": {"type": "number"},
                    "days_elapsed_in_month": {"type": "integer"},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="plan_cache",
            description="Plan cache breakpoints for prompt reuse",
            inputSchema={
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {
                                    "type": "string",
                                    "enum": ["system", "user", "assistant"],
                                },
                                "content": {"type": "string"},
                                "label": {"type": "string"},
                            },
                            "required": ["role", "content"],
                        },
                    },
                    "expected_reuse_count": {
                        "type": "integer",
                        "default": 2,
                        "minimum": 1,
                    },
                    "model": {
                        "type": "string",
                        "default": "claude-sonnet-4-6",
                    },
                },
                "required": ["messages"],
            },
        ),
        Tool(
            name="batch_prompts",
            description="Batch multiple tasks into one prompt",
            inputSchema={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 5,
                    },
                    "role": {"type": "string", "default": "general"},
                    "model": {
                        "type": "string",
                        "default": "claude-sonnet-4-6",
                    },
                },
                "required": ["tasks"],
            },
        ),
        Tool(
            name="summarize_thread",
            description="Compress conversation for fresh thread",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation": {"type": "string"},
                    "max_tokens": {
                        "type": "integer",
                        "default": 500,
                        "minimum": 100,
                        "maximum": 2000,
                    },
                    "model": {
                        "type": "string",
                        "default": "claude-sonnet-4-6",
                    },
                },
                "required": ["conversation"],
            },
        ),
        Tool(
            name="get_session_stats",
            description="Get session statistics",
            inputSchema={
                "type": "object",
                "properties": {
                    "since": {
                        "type": "string",
                        "description": "ISO 8601 timestamp filter",
                    }
                },
            },
        ),
        Tool(
            name="compare_providers",
            description="Compare cost of same request across Claude, OpenAI, and Gemini",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Request text to cost-compare"},
                    "model": {
                        "type": "string",
                        "default": "claude-sonnet-4-6",
                        "description": "Model for token counting",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="reload_config",
            description="Reload pricing/providers/roles YAML files without restarting server",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ping_session",
            description="Record session activity to reset idle clock. Call on each user interaction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Existing session ID. Omit to create new session.",
                    }
                },
            },
        ),
        Tool(
            name="check_session_timeout",
            description="Check if session has exceeded idle thresholds. Returns status: active/warn/expired.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "idle_threshold_minutes": {
                        "type": "integer",
                        "default": 30,
                        "minimum": 1,
                        "description": "Minutes of inactivity before session expires",
                    },
                    "warn_threshold_minutes": {
                        "type": "integer",
                        "default": 20,
                        "minimum": 1,
                        "description": "Minutes of inactivity before warning",
                    },
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="clear_history",
            description="Delete usage history records older than N days for data retention compliance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "older_than_days": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Delete records older than this many days",
                    }
                },
                "required": ["older_than_days"],
            },
        ),
        Tool(
            name="export_stats",
            description="Export usage history as JSON array or CSV for FinOps reporting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "since": {
                        "type": "string",
                        "description": "ISO 8601 timestamp filter (optional)",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "csv"],
                        "default": "json",
                    },
                },
            },
        ),
        Tool(
            name="auto_compact",
            description=(
                "Auto-compact conversation turns when token threshold is exceeded. "
                "Returns status=ok (no action needed) or status=compacted (use returned "
                "compacted_turns as new context). Call each turn for automatic management."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "turns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["role", "content"],
                        },
                        "description": "Conversation turns in chronological order",
                    },
                    "model": {
                        "type": "string",
                        "default": "claude-sonnet-4-6",
                        "description": "Model for token counting and context window lookup",
                    },
                    "threshold_pct": {
                        "type": "number",
                        "description": "Override config threshold_pct (fraction of context window)",
                    },
                    "threshold_tokens": {
                        "type": "integer",
                        "description": "Override config threshold_tokens (absolute token count)",
                    },
                },
                "required": ["turns"],
            },
        ),
    ]


async def call_tool(ctx: ServerContext, name: str, arguments: dict) -> str:
    """Dispatch tool calls (module-level for testing)."""
    try:
        if name == "rewrite_prompt":
            result = ctx.rewriter.rewrite(
                arguments.get("text", ""),
                role=arguments.get("role", "general"),
                model=arguments.get("model", "claude-sonnet-4-6"),
            )
            await ctx.stats.record(
                tool="rewrite_prompt",
                model=arguments.get("model") or ctx.config.default_model,
                input_tokens=result.raw_tokens,
                output_tokens=0,
                saving_pct=result.saving_pct,
            )
            return json.dumps({
                "rewritten": result.rewritten,
                "saving_pct": result.saving_pct,
                "warning": result.warning,
            })

        elif name == "optimize_context":
            result = ctx.optimizer.optimize(
                arguments.get("context", ""),
                token_budget=arguments.get("token_budget", 2000),
                model=arguments.get("model", "claude-sonnet-4-6"),
            )
            await ctx.stats.record(
                tool="optimize_context",
                model=arguments.get("model") or ctx.config.default_model,
                input_tokens=result.raw_tokens,
                output_tokens=0,
                saving_pct=result.saving_pct,
            )
            return json.dumps({
                "optimized": result.optimized,
                "saving_pct": result.saving_pct,
                "chunks_dropped": result.chunks_dropped,
            })

        elif name == "route_request":
            result = ctx.router.route(
                arguments.get("text", ""),
                intent=arguments.get("intent", "auto"),
                stakes=arguments.get("stakes", "auto"),
                provider=arguments.get("provider", "claude"),
                monthly_budget_usd=arguments.get("monthly_budget_usd"),
                days_elapsed_in_month=arguments.get("days_elapsed_in_month"),
            )
            await ctx.stats.record(
                tool="route_request",
                model=result.recommended_model,
                input_tokens=result.input_tokens,
            )
            return json.dumps({
                "recommended_model": result.recommended_model,
                "reason": result.reason,
                "intent_detected": result.intent_detected,
                "stakes_detected": result.stakes_detected,
                "estimated_input_cost_usd": result.estimated_input_cost_usd,
                "context_window_pct": result.context_window_pct,
                "task_budget_recommended": result.task_budget_recommended,
                "peak_hour_warning": result.peak_hour_warning,
                "cost_floor_breached": result.cost_floor_breached,
                "alternatives": result.alternatives,
                "batch_recommended": result.batch_recommended,
                "batch_recommendation_note": (
                    "Batch API available: 50% cost reduction for this task type. "
                    "Use Anthropic batch mode for non-time-sensitive workloads."
                ) if result.batch_recommended else None,
            })

        elif name == "plan_cache":
            result = ctx.cache_planner.plan(
                arguments.get("messages", []),
                expected_reuse_count=arguments.get("expected_reuse_count", 2),
                model=arguments.get("model", "claude-sonnet-4-6"),
            )
            await ctx.stats.record(
                tool="plan_cache",
                model=arguments.get("model") or ctx.config.default_model,
                saving_pct=result.savings_pct,
            )
            return json.dumps({
                "breakpoints": [
                    {
                        "message_index": bp.message_index,
                        "ttl": bp.ttl,
                        "rationale": bp.rationale,
                    }
                    for bp in result.breakpoints
                ],
                "savings_pct": result.savings_pct,
            })

        elif name == "batch_prompts":
            result = ctx.batcher.batch(
                arguments.get("tasks", []),
                role=arguments.get("role", "general"),
                model=arguments.get("model", "claude-sonnet-4-6"),
            )
            await ctx.stats.record(
                tool="batch_prompts",
                model=arguments.get("model") or ctx.config.default_model,
                input_tokens=result.individual_tokens,
                saving_pct=result.saving_pct,
            )
            return json.dumps({
                "batched_prompt": result.batched_prompt,
                "saving_pct": result.saving_pct,
            })

        elif name == "summarize_thread":
            result = ctx.summarizer.summarize(
                arguments.get("conversation", ""),
                max_tokens=arguments.get("max_tokens", 500),
                model=arguments.get("model", "claude-sonnet-4-6"),
            )
            await ctx.stats.record(
                tool="summarize_thread",
                model=arguments.get("model") or ctx.config.default_model,
                input_tokens=result.original_tokens,
                output_tokens=result.summary_tokens,
                saving_pct=result.saving_pct,
            )
            return json.dumps({
                "summary": result.summary,
                "reset_prompt": result.reset_prompt,
                "saving_pct": result.saving_pct,
            })

        elif name == "get_session_stats":
            snapshot = await ctx.stats.snapshot(
                since=arguments.get("since")
            )
            from datetime import datetime, timezone, date
            last_verified = ctx.config.last_verified
            pricing_age_days = None
            stale_pricing_warning = None
            try:
                verified_date = date.fromisoformat(last_verified)
                pricing_age_days = (date.today() - verified_date).days
                if pricing_age_days > 90:
                    stale_pricing_warning = (
                        f"pricing.yaml last verified {pricing_age_days} days ago "
                        f"({last_verified}). Rates may be outdated. Update pricing.yaml."
                    )
            except Exception:
                pass
            total_savings_usd = round(
                snapshot.total_cost_usd * (snapshot.avg_saving_pct / 100), 6
            ) if snapshot.avg_saving_pct else 0.0
            return json.dumps({
                "total_calls": snapshot.total_calls,
                "total_cost_usd": snapshot.total_cost_usd,
                "total_savings_usd": total_savings_usd,
                "avg_saving_pct": snapshot.avg_saving_pct,
                "cache_hit_rate": snapshot.cache_hit_rate,
                "calls_by_tool": snapshot.calls_by_tool,
                "cost_by_model": snapshot.cost_by_model,
                "calls_by_model": snapshot.calls_by_model,
                "tokens_by_model": snapshot.tokens_by_model,
                "pricing_age_days": pricing_age_days,
                "stale_pricing_warning": stale_pricing_warning,
            })

        elif name == "compare_providers":
            comparisons = ctx.router.compare_providers(
                arguments.get("text", ""),
                model=arguments.get("model", "claude-sonnet-4-6"),
            )
            return json.dumps({"comparisons": comparisons})

        elif name == "reload_config":
            ctx.config = load_config()
            ctx.rewriter = Rewriter(ctx.config)
            ctx.optimizer = Optimizer(ctx.config)
            return json.dumps({"reloaded": True})

        elif name == "ping_session":
            result = await ctx.session_manager.ping(
                session_id=arguments.get("session_id")
            )
            return json.dumps({
                "session_id": result.session_id,
                "started_ts": result.started_ts,
                "last_ping_ts": result.last_ping_ts,
                "is_new": result.is_new,
            })

        elif name == "check_session_timeout":
            idle_threshold = arguments.get(
                "idle_threshold_minutes",
                ctx.config.timeout.idle_threshold_minutes,
            )
            warn_threshold = arguments.get(
                "warn_threshold_minutes",
                ctx.config.timeout.warn_threshold_minutes,
            )
            result = await ctx.session_manager.check_timeout(
                session_id=arguments.get("session_id", ""),
                idle_threshold_minutes=idle_threshold,
                warn_threshold_minutes=warn_threshold,
            )
            return json.dumps({
                "session_id": result.session_id,
                "status": result.status,
                "idle_minutes": result.idle_minutes,
                "recommended_action": result.recommended_action,
                "message": result.message,
            })

        elif name == "clear_history":
            older_than_days = arguments.get("older_than_days", 90)
            deleted = await ctx.stats.clear_old(older_than_days=older_than_days)
            return json.dumps({
                "deleted_count": deleted,
                "older_than_days": older_than_days,
            })

        elif name == "export_stats":
            exported = await ctx.stats.export(
                since=arguments.get("since"),
                format=arguments.get("format", "json"),
            )
            return exported

        elif name == "auto_compact":
            result = ctx.compactor.compact(
                turns=arguments.get("turns", []),
                model=arguments.get("model", "claude-sonnet-4-6"),
                threshold_pct=arguments.get("threshold_pct"),
                threshold_tokens=arguments.get("threshold_tokens"),
            )
            await ctx.stats.record(
                tool="auto_compact",
                model=arguments.get("model") or ctx.config.default_model,
                input_tokens=result.original_tokens,
                output_tokens=result.compacted_tokens,
                saving_pct=result.saving_pct,
            )
            return json.dumps({
                "status": result.status,
                "original_tokens": result.original_tokens,
                "compacted_tokens": result.compacted_tokens,
                "turns_kept": result.turns_kept,
                "turns_dropped": result.turns_dropped,
                "saving_pct": result.saving_pct,
                "compacted_turns": result.compacted_turns,
                "threshold_used": result.threshold_used,
            })

        else:
            return json.dumps({
                "error": f"Unknown tool: {name}",
                "type": "UnknownTool",
                "tool": name,
            })

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "type": type(e).__name__,
            "tool": name,
        })


async def main() -> None:
    """Run MCP server."""
    config_dir = Path(__file__).resolve().parents[2]  # project root: src/promptwise/ -> src/ -> root
    config = load_config(config_dir)
    db_path = Path.home() / ".promptwise" / "history.db"
    await init_db(db_path)

    ctx = ServerContext(
        config=config,
        rewriter=Rewriter(config),
        optimizer=Optimizer(config),
        router=Router(config),
        cache_planner=CachePlanner(config),
        batcher=Batcher(config),
        summarizer=Summarizer(config),
        stats=StatsService(config, db_path),
        session_manager=SessionManager(db_path),
        compactor=Compactor(config),
    )

    server = Server("promptwise")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return await list_tools(ctx)

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        result = await call_tool(ctx, name, arguments)
        return [TextContent(type="text", text=result)]

    init_opts = InitializationOptions(
        server_name="promptwise",
        server_version="1.0.0",
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, initialization_options=init_opts)


if __name__ == "__main__":
    asyncio.run(main())
