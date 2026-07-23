"""PromptWise — Unified MCP server with ALL tools."""

import asyncio
import importlib
import json
import sys
from pathlib import Path

from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path = [p for p in sys.path if p not in ("", str(Path.cwd()))]

from promptwise.config import load_config
from promptwise.core import (
    Router, Rewriter, Optimizer, CompressionEngine, CachePlanner,
    Batcher, Summarizer, RoleDetector, Orchestrator, QualityGuard,
    SkillLoader, WorkflowPlanner, TaskTracker,
)
from promptwise.security import SecurityScanner, ComplianceEngine
from promptwise.plugins import BudgetGuardian, CodeValidator, CostMonitor, ROITracker
from promptwise.db import init_db, SessionManager, MemoryManager
from promptwise.core.tool_registry import ServerContext, ToolRegistry, _registry, _get_audit_log  # noqa: F401 (ToolRegistry: tests/test_tool_registry_decorator.py imports it from here; _get_audit_log: back-compat re-export, canonical copy lives in tool_registry.py)


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


# route_request/rewrite_prompt/optimize_context/compress_prompt/
# plan_cache/cache_lookup/cache_store/cache_stats/batch_prompts/
# summarize_thread/compare_providers (handlers.optimization) originally sat
# right here, in the unsectioned preamble block before Security -- register
# at this position to preserve tool registration order. (The stray
# _maybe_alert_budget definition previously left here after Task 18 moved
# monitor_budget's real copy to handlers/budget_cost.py is dead code and is
# removed in this same edit -- it had no remaining callers.)
_add_handler_module("optimization")


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


# agile_plan/shard_doc/draft_story/run_quality_gate/check_policy/
# record_audit/export_audit/sync_agent_config/detect_agents/
# build_context_model/propose_agent_config/lint_agent_config/
# check_portability/export_web_bundle (handlers.agile) originally sat right
# here, between compare_providers/Energy&Routing and Continuous learning --
# register at this position to preserve tool registration order (largest
# category, 14 tools).
_add_handler_module("agile")


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
from promptwise.handlers.optimization import _handle_route_request, _handle_rewrite_prompt, _handle_optimize_context, _handle_compress_prompt, _handle_plan_cache, _handle_cache_lookup, _handle_cache_store, _handle_cache_stats, _handle_batch_prompts, _handle_summarize_thread, _handle_compare_providers  # noqa: F401
from promptwise.handlers.agile import _handle_agile_plan, _handle_shard_doc, _handle_draft_story, _handle_run_quality_gate, _handle_check_policy, _handle_record_audit, _handle_export_audit, _handle_sync_agent_config, _handle_detect_agents, _handle_build_context_model, _handle_propose_agent_config, _handle_lint_agent_config, _handle_check_portability, _handle_export_web_bundle  # noqa: F401

_TOOL_DEFS = [entry.tool for entry in _registry.entries.values()]
_HANDLERS = {name: entry.handler for name, entry in _registry.entries.items()}

if __name__ == "__main__":
    asyncio.run(main())
