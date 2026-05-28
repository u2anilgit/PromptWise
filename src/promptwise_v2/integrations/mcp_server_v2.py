import asyncio
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Ensure v1 is importable
sys.path = [p for p in sys.path if p not in ("", str(Path.cwd()))]

from promptwise.batcher import Batcher
from promptwise.cache_planner import CachePlanner
from promptwise.compactor import Compactor
from promptwise.config import load_config
from promptwise.db import init_db
from promptwise.optimizer import Optimizer
from promptwise.rewriter import Rewriter
from promptwise.router import Router
from promptwise.session_manager import SessionManager
from promptwise.stats import StatsService
from promptwise.summarizer import Summarizer

from promptwise_v2.config_v2 import load_config_v2
from promptwise_v2.core.security import SecurityChecker
from promptwise_v2.core.role_intelligence import RoleIntelligence
from promptwise_v2.core.orchestrator import Orchestrator
from promptwise_v2.core.compression_engine import CompressionEngine
from promptwise_v2.core.memory_manager import MemoryManager
from promptwise_v2.core.router_v2 import RouterV2
from promptwise_v2.plugins.budget_guardian import BudgetGuardian
from promptwise_v2.plugins.code_validator import CodeValidator
from promptwise_v2.plugins.roi_tracker import ROITracker
from promptwise_v2.plugins.monitoring import CostMonitor


@dataclass
class ServerContextV2:
    # v1 services
    rewriter: Rewriter
    optimizer: object
    router: Router
    cache_planner: CachePlanner
    batcher: Batcher
    summarizer: Summarizer
    stats: StatsService
    session_manager: SessionManager
    compactor: Compactor
    config: object
    # v2 services
    security: SecurityChecker
    role_intel: RoleIntelligence
    orchestrator: Orchestrator
    compression: CompressionEngine
    memory: MemoryManager
    budget_guardian: BudgetGuardian
    code_validator: CodeValidator
    roi_tracker: ROITracker
    cost_monitor: CostMonitor


_V2_TOOL_DEFS = [
    Tool(name="security_check",
         description="Run 5-level security check (syntax injection, secrets, destructive, supply_chain, permissions)",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
    Tool(name="detect_role",
         description="Detect organizational role (developer/analyst/researcher/manager/writer/designer) from prompt",
         inputSchema={"type": "object", "properties": {
             "text": {"type": "string"},
             "explanation_mode": {"type": "boolean", "default": False},
         }, "required": ["text"]}),
    Tool(name="orchestrate_tasks",
         description="Parse multi-step prompt into DAG and execute with failure strategy (stop/retry/fallback/all)",
         inputSchema={"type": "object", "properties": {
             "text": {"type": "string"},
             "strategy": {"type": "string", "enum": ["stop", "retry", "fallback", "all"], "default": "fallback"},
         }, "required": ["text"]}),
    Tool(name="monitor_budget",
         description="Check spend against budget limit, returns alert_level (ok/warn/critical/hard_stop)",
         inputSchema={"type": "object", "properties": {
             "used_usd": {"type": "number"},
             "days_elapsed": {"type": "integer", "default": 1},
         }, "required": ["used_usd"]}),
    Tool(name="validate_output",
         description="Validate generated code for syntax errors and hallucinated imports",
         inputSchema={"type": "object", "properties": {
             "code": {"type": "string"},
             "language": {"type": "string", "default": "python"},
         }, "required": ["code"]}),
    Tool(name="track_roi",
         description="Calculate ROI ratio: value of time saved vs. cost incurred",
         inputSchema={"type": "object", "properties": {
             "session_id": {"type": "string"},
             "total_cost_usd": {"type": "number"},
             "tokens_saved": {"type": "integer"},
             "calls": {"type": "integer"},
         }, "required": ["session_id", "total_cost_usd", "tokens_saved", "calls"]}),
    Tool(name="get_memory_context",
         description="Retrieve past memory entries for a session",
         inputSchema={"type": "object", "properties": {
             "session_id": {"type": "string"},
             "limit": {"type": "integer", "default": 20},
         }, "required": ["session_id"]}),
    Tool(name="compress_prompt",
         description="Apply caveman compression: remove articles, filler, pleasantries, hedging",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
    Tool(name="route_for_plugin",
         description="Detect which plugin should handle this request (monitoring/codereview_bridge/playwright_bridge)",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
    Tool(name="check_energy",
         description="Get energy efficiency score for a model (1.0=most efficient, 0.0=least)",
         inputSchema={"type": "object", "properties": {
             "model": {"type": "string"},
             "tokens": {"type": "integer", "default": 1000},
         }, "required": ["model"]}),
]

_V1_NAMES = {
    "rewrite_prompt", "optimize_context", "route_request", "plan_cache",
    "batch_prompts", "summarize_thread", "get_session_stats", "compare_providers",
    "reload_config", "ping_session", "check_session_timeout", "clear_history",
    "export_stats", "auto_compact",
}


async def list_tools_v2() -> list[Tool]:
    from promptwise.server import list_tools as _v1_list
    v1 = await _v1_list()
    return v1 + _V2_TOOL_DEFS


async def build_ctx_v2(config_dir: Path) -> ServerContextV2:
    config_dir = Path(config_dir)
    # v1 configs (pricing.yaml, providers.yaml, roles.yaml) may live in the
    # project root rather than the config/ subdirectory passed by callers.
    v1_config_dir = config_dir
    if not (config_dir / "pricing.yaml").exists() and (config_dir.parent / "pricing.yaml").exists():
        v1_config_dir = config_dir.parent
    v1_config = load_config(v1_config_dir)
    db_path = Path(tempfile.mktemp(suffix=".db"))
    await init_db(db_path)
    mm = MemoryManager(db_path)
    await mm.init()
    cfg_v2 = load_config_v2(config_dir)
    return ServerContextV2(
        rewriter=Rewriter(v1_config),
        optimizer=Optimizer(v1_config),
        router=Router(v1_config),
        cache_planner=CachePlanner(v1_config),
        batcher=Batcher(v1_config),
        summarizer=Summarizer(v1_config),
        stats=StatsService(v1_config, db_path),
        session_manager=SessionManager(db_path),
        compactor=Compactor(v1_config),
        config=v1_config,
        security=SecurityChecker(),
        role_intel=RoleIntelligence(),
        orchestrator=Orchestrator(),
        compression=CompressionEngine(),
        memory=mm,
        budget_guardian=BudgetGuardian(
            limit_usd=cfg_v2.policies.budget_hard_stop_usd,
            team_budget_usd=cfg_v2.policies.team_budget_usd,
        ),
        code_validator=CodeValidator(),
        roi_tracker=ROITracker(),
        cost_monitor=CostMonitor(),
    )


async def call_tool_v2(ctx: ServerContextV2, name: str, arguments: dict) -> str:
    if name in _V1_NAMES:
        from promptwise.server import call_tool as _v1_call, ServerContext as V1Ctx
        v1_ctx = V1Ctx(
            config=ctx.config, rewriter=ctx.rewriter, optimizer=ctx.optimizer,
            router=ctx.router, cache_planner=ctx.cache_planner, batcher=ctx.batcher,
            summarizer=ctx.summarizer, stats=ctx.stats, session_manager=ctx.session_manager,
            compactor=ctx.compactor,
        )
        return await _v1_call(v1_ctx, name, arguments)

    try:
        if name == "security_check":
            r = ctx.security.check(arguments.get("text", ""))
            return json.dumps({"passed": r.passed, "risk_score": r.risk_score,
                               "violations": r.violations, "blocked": r.blocked,
                               "details": r.details})

        elif name == "detect_role":
            r = ctx.role_intel.detect(arguments.get("text", ""),
                                      explanation_mode=arguments.get("explanation_mode", False))
            return json.dumps({"role": r.role, "confidence": r.confidence,
                               "recommended_model_tier": r.recommended_model_tier,
                               "context_hint": r.context_hint,
                               "keywords_matched": r.keywords_matched})

        elif name == "orchestrate_tasks":
            r = ctx.orchestrator.execute(arguments.get("text", ""),
                                         strategy=arguments.get("strategy", "fallback"))
            return json.dumps({"task_id": r.task_id, "status": r.status,
                               "steps_total": r.steps_total, "steps_done": r.steps_done,
                               "strategy_used": r.strategy_used, "output": r.output,
                               "duration_ms": r.duration_ms, "error": r.error})

        elif name == "monitor_budget":
            r = ctx.budget_guardian.check(
                used_usd=float(arguments.get("used_usd", 0.0)),
                days_elapsed=int(arguments.get("days_elapsed", 1)),
            )
            return json.dumps({"used_usd": r.used_usd, "limit_usd": r.limit_usd,
                               "pct_used": r.pct_used, "daily_burn_usd": r.daily_burn_usd,
                               "projected_monthly_usd": r.projected_monthly_usd,
                               "alert_level": r.alert_level})

        elif name == "validate_output":
            r = ctx.code_validator.validate(
                arguments.get("code", ""),
                language=arguments.get("language", "python"),
            )
            return json.dumps({"valid": r.valid, "issues": r.issues,
                               "confidence": r.confidence, "checks_run": r.checks_run,
                               "suggested_fix": r.suggested_fix})

        elif name == "track_roi":
            r = ctx.roi_tracker.calculate(
                session_id=arguments.get("session_id", ""),
                total_cost_usd=float(arguments.get("total_cost_usd", 0.0)),
                tokens_saved=int(arguments.get("tokens_saved", 0)),
                calls=int(arguments.get("calls", 1)),
            )
            return json.dumps({"roi_ratio": r.roi_ratio,
                               "estimated_time_saved_min": r.estimated_time_saved_min,
                               "productivity_score": r.productivity_score,
                               "total_cost_usd": r.total_cost_usd})

        elif name == "get_memory_context":
            entries = await ctx.memory.get_context(
                session_id=arguments.get("session_id", ""),
                limit=int(arguments.get("limit", 20)),
            )
            return json.dumps([{"entry_id": e.entry_id, "tool": e.tool,
                                "summary": e.summary, "ts": e.ts} for e in entries])

        elif name == "compress_prompt":
            r = ctx.compression.compress(arguments.get("text", ""))
            return json.dumps({"compressed": r.compressed, "saving_pct": r.saving_pct,
                               "tokens_saved": r.tokens_saved, "rules_applied": r.rules_applied})

        elif name == "route_for_plugin":
            plugin = RouterV2().route_for_plugin(arguments.get("text", ""))
            return json.dumps({"plugin": plugin})

        elif name == "check_energy":
            score = ctx.cost_monitor.energy_efficiency_score(
                model=arguments.get("model", ""),
                tokens=int(arguments.get("tokens", 1000)),
            )
            return json.dumps({"energy_efficiency_score": score,
                               "model": arguments.get("model")})

        else:
            return json.dumps({"error": f"Unknown tool: {name}", "tool": name})

    except Exception as e:
        return json.dumps({"error": str(e), "type": type(e).__name__, "tool": name})


async def main() -> None:
    config_dir = Path(__file__).resolve().parents[3]
    ctx = await build_ctx_v2(config_dir)
    server = Server("promptwise-v2")

    @server.list_tools()
    async def _list():
        return await list_tools_v2()

    @server.call_tool()
    async def _call(name: str, arguments: dict):
        result = await call_tool_v2(ctx, name, arguments)
        return [TextContent(type="text", text=result)]

    init_opts = InitializationOptions(
        server_name="promptwise-v2",
        server_version="2.0.0",
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )
    async with stdio_server() as (r, w):
        await server.run(r, w, initialization_options=init_opts)


if __name__ == "__main__":
    asyncio.run(main())
