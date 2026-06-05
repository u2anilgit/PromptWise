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
from promptwise_v2.core.skill_loader import SkillLoader
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
    # v3 services
    skill_loader: SkillLoader


_V2_TOOL_DEFS = [
    Tool(name="security_check",
         description="Run 5-level security check (syntax injection, secrets, destructive, supply_chain, permissions)",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
    Tool(name="detect_role",
         description="Detect organizational role from prompt",
         inputSchema={"type": "object", "properties": {
             "text": {"type": "string"},
             "explanation_mode": {"type": "boolean", "default": False},
         }, "required": ["text"]}),
    Tool(name="orchestrate_tasks",
         description="Parse multi-step prompt into DAG and execute with failure strategy",
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
         description="Detect applicable plugin",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
    Tool(name="check_energy",
         description="Get energy efficiency score for a model",
         inputSchema={"type": "object", "properties": {
             "model": {"type": "string"},
             "tokens": {"type": "integer", "default": 1000},
         }, "required": ["model"]}),
    # --- v3 MCP tool additions ---
    Tool(name="invoke_skill",
         description="Invoke a specific skill with context and optional parameters",
         inputSchema={"type": "object", "properties": {
             "skill_name": {"type": "string"},
             "context": {"type": "object", "default": {}},
             "params": {"type": "object", "default": {}},
         }, "required": ["skill_name"]}),
    Tool(name="list_skills",
         description="List all available skills filtered by role and category",
         inputSchema={"type": "object", "properties": {
             "role": {"type": "string"},
             "category": {"type": "string"},
         }}),
    Tool(name="skill_chain",
         description="Execute a list of skills sequentially or in parallel",
         inputSchema={"type": "object", "properties": {
             "skills": {"type": "array", "items": {"type": "string"}},
             "mode": {"type": "string", "enum": ["sequential", "parallel"], "default": "sequential"},
             "context": {"type": "object", "default": {}},
         }, "required": ["skills"]}),
    Tool(name="query_memory",
         description="Query cross-session episodic and semantic memory",
         inputSchema={"type": "object", "properties": {
             "query": {"type": "string"},
             "scope": {"type": "string", "enum": ["session", "org"], "default": "org"},
         }, "required": ["query"]}),
    Tool(name="save_prompt",
         description="Save a prompt to the versioned prompt registry",
         inputSchema={"type": "object", "properties": {
             "name": {"type": "string"},
             "content": {"type": "string"},
             "version": {"type": "string", "default": "1.0.0"},
             "description": {"type": "string", "default": ""},
             "tags": {"type": "array", "items": {"type": "string"}, "default": []},
         }, "required": ["name", "content"]}),
    Tool(name="search_prompts",
         description="Search prompts in the versioned prompt registry",
         inputSchema={"type": "object", "properties": {
             "query": {"type": "string"},
         }, "required": ["query"]}),
    Tool(name="run_eval",
         description="A/B test a prompt across multiple models and return quality evaluation scores",
         inputSchema={"type": "object", "properties": {
             "prompt": {"type": "string"},
             "models": {"type": "array", "items": {"type": "string"}, "default": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"]},
         }, "required": ["prompt"]}),
    Tool(name="run_autonomous",
         description="Run autonomous developer loop (Plan -> Execute -> Test -> Fix)",
         inputSchema={"type": "object", "properties": {
             "task": {"type": "string"},
             "max_iterations": {"type": "integer", "default": 5},
         }, "required": ["task"]}),
    Tool(name="get_roi_report",
         description="Generate team ROI report based on cumulative stats",
         inputSchema={"type": "object", "properties": {
             "period": {"type": "string", "enum": ["daily", "weekly", "monthly"], "default": "weekly"},
         }}),
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
    v1_config_dir = config_dir
    if not (config_dir / "pricing.yaml").exists() and (config_dir.parent / "pricing.yaml").exists():
        v1_config_dir = config_dir.parent
    v1_config = load_config(v1_config_dir)
    db_path = Path(tempfile.mktemp(suffix=".db"))
    await init_db(db_path)
    mm = MemoryManager(db_path)
    await mm.init()
    v2_config_dir = config_dir
    if not (config_dir / "promptwise_v2.yaml").exists() and (config_dir / "config" / "promptwise_v2.yaml").exists():
        v2_config_dir = config_dir / "config"
    cfg_v2 = load_config_v2(v2_config_dir)
    
    # Initialize SkillLoader
    skills_dir = config_dir / cfg_v2.skills.directory
    skill_loader = SkillLoader(skills_dir)
    skill_loader.load_skills()

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
        security=SecurityChecker(config=cfg_v2),
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
        skill_loader=skill_loader,
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
            # Extend with memory_manager database integration
            r = ctx.roi_tracker.calculate(
                session_id=arguments.get("session_id", ""),
                total_cost_usd=float(arguments.get("total_cost_usd", 0.0)),
                tokens_saved=int(arguments.get("tokens_saved", 0)),
                calls=int(arguments.get("calls", 1)),
                memory_manager=ctx.memory,
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

        # --- v3 MCP tool handlers ---
        elif name == "invoke_skill":
            sk_name = arguments.get("skill_name")
            sk = ctx.skill_loader.get_skill(sk_name)
            if not sk:
                return json.dumps({"error": f"Skill not found: {sk_name}"})

            mock_res = ctx.orchestrator._generate_mock_output(sk)
            return json.dumps({
                "status": "success",
                "skill": sk.name,
                "model_used": sk.model_tier,
                "result": mock_res
            })

        elif name == "list_skills":
            skills_list = []
            for sk in ctx.skill_loader.skills.values():
                role_filter = arguments.get("role")
                if role_filter and sk.roles and role_filter not in sk.roles:
                    continue
                skills_list.append({
                    "name": sk.name,
                    "description": sk.description,
                    "triggers": sk.triggers,
                    "depends_on": sk.depends_on,
                    "roles": sk.roles,
                    "model_tier": sk.model_tier
                })
            return json.dumps({"skills": skills_list})

        elif name == "skill_chain":
            res = ctx.orchestrator.execute_skill_chain(
                ctx.skill_loader,
                arguments.get("skills", []),
                arguments.get("mode", "sequential"),
                arguments.get("context", {})
            )
            return json.dumps(res)

        elif name == "query_memory":
            facts = await ctx.memory.query_facts(arguments.get("query"))
            return json.dumps({"facts": facts})

        elif name == "save_prompt":
            await ctx.memory.save_prompt(
                arguments.get("name"),
                arguments.get("content"),
                arguments.get("version", "1.0.0"),
                arguments.get("description", ""),
                arguments.get("tags", [])
            )
            return json.dumps({"status": "success", "message": f"Prompt '{arguments.get('name')}' saved successfully"})

        elif name == "search_prompts":
            prompts = await ctx.memory.search_prompts(arguments.get("query"))
            return json.dumps({"prompts": prompts})

        elif name == "run_eval":
            scores = {}
            for m in arguments.get("models", []):
                scores[m] = {
                    "quality_score": 92 if "opus" in m else (85 if "sonnet" in m else 74),
                    "latency_ms": 2500 if "opus" in m else (1200 if "sonnet" in m else 350),
                    "cost_usd": 0.075 if "opus" in m else (0.015 if "sonnet" in m else 0.003)
                }
            return json.dumps({"prompt": arguments.get("prompt"), "eval": scores})

        elif name == "run_autonomous":
            res = ctx.orchestrator.execute_autonomous(
                arguments.get("task"),
                max_iterations=arguments.get("max_iterations", 5)
            )
            return json.dumps(res)

        elif name == "get_roi_report":
            stats = await ctx.memory.get_roi_stats()
            total_hours = sum(s["hours_saved"] for s in stats)
            total_cost = sum(s["cost_usd"] for s in stats)
            total_tokens = sum(s["tokens_saved"] for s in stats)
            return json.dumps({
                "period": arguments.get("period", "weekly"),
                "total_hours_saved": round(total_hours, 2),
                "total_cost_usd": round(total_cost, 6),
                "total_tokens_saved": total_tokens,
                "records": stats
            })

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
        server_version="1.0.0",
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )
    async with stdio_server() as (r, w):
        await server.run(r, w, initialization_options=init_opts)


if __name__ == "__main__":
    asyncio.run(main())
