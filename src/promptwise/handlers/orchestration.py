"""handlers.orchestration -- orchestration MCP tool handlers (moved
verbatim from server.py's "Orchestration" section during the handlers/
package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


def _fleet_planning_hints(tasks_arg: list[dict]) -> tuple[dict, dict]:
    """Best-effort agent_priority/agent_budget_status maps for plan_waves(),
    built from the registered agents any of `tasks_arg`'s "agent_id" values
    reference. Fail-soft: a broken/missing FleetRegistry (or no agent_ids
    present at all) yields two empty dicts, which is byte-identical to
    calling plan_waves() without these WP5 kwargs at all.

    Note on `remaining_usd`: WP5 is planning-level only -- there is no live
    spend tracking yet, so this is the agent's registered `budget_usd`
    ceiling as of registration time, not a decrementing live balance.
    register_agent's own default is budget_usd=0.0, which means "no budget
    configured" (unlimited), not "zero remaining budget" -- so an agent is
    only added to the map when its configured budget_usd is > 0. An agent
    absent from the map is never treated as over budget (plan_waves()
    defaults an unknown agent_id to solvent)."""
    agent_ids = {t.get("agent_id") for t in tasks_arg if t.get("agent_id")}
    if not agent_ids:
        return {}, {}
    try:
        from promptwise.core.fleet import FleetRegistry
        registry = FleetRegistry()
        priority: dict = {}
        budget_status: dict = {}
        for agent_id in agent_ids:
            agent = registry.get(agent_id)
            if agent is None:
                continue
            priority[agent_id] = agent["priority"]
            if agent["budget_usd"] > 0:
                budget_status[agent_id] = {"remaining_usd": agent["budget_usd"]}
        return priority, budget_status
    except Exception:
        return {}, {}


@tool(name="orchestrate_tasks", description="Parse a multi-step prompt into a DAG and execute with a failure strategy. Pass 'tasks' (with depends_on / file) to instead emit a safe parallel wave plan (which tasks can run at once) for the caller to dispatch.",
         schema={"type": "object", "properties": {
             "text": {"type": "string"}, "strategy": {"type": "string", "enum": ["stop", "retry", "fallback", "all"], "default": "fallback"},
             "tasks": {"type": "array", "description": "Structured tasks [{id, depends_on:[ids], file, agent_id}] — when present, returns a wave plan instead of executing",
                       "items": {"type": "object", "properties": {
                           "id": {"type": "string"}, "depends_on": {"type": "array", "items": {"type": "string"}}, "file": {"type": "string"},
                           "agent_id": {"type": "string", "default": ""}}}},
             "fan_out_cap": {"type": "integer", "default": 8, "description": "Max tasks per parallel wave"}},
         "required": ["text"]})
async def _handle_orchestrate_tasks(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.task_graph import plan_waves, summarize_plan
    fan_out = int(arguments.get("fan_out_cap", 8))
    tasks_arg = arguments.get("tasks")
    if isinstance(tasks_arg, list) and tasks_arg:
        # emit-not-execute: which tasks are safe to run in parallel
        priority, budget_status = _fleet_planning_hints(tasks_arg)
        plan = plan_waves(tasks_arg, fan_out_cap=fan_out, agent_priority=priority, agent_budget_status=budget_status)
        plan["summary"] = summarize_plan(plan)
        return json.dumps({"mode": "plan", **plan})
    r = ctx.orchestrator.execute(arguments.get("text", ""), strategy=arguments.get("strategy", "fallback"))
    # additive: emit a wave plan from the parsed steps (narrative order = sequential)
    parsed = ctx.orchestrator.parse_tasks(arguments.get("text", ""))
    seq = [{"id": t["id"], "depends_on": ([parsed[i - 1]["id"]] if i > 0 else [])}
           for i, t in enumerate(parsed)]
    wave_plan = plan_waves(seq, fan_out_cap=fan_out)
    wave_plan["summary"] = summarize_plan(wave_plan)
    return json.dumps({"task_id": r.task_id, "status": r.status, "steps_total": r.steps_total, "steps_done": r.steps_done,
                       "strategy_used": r.strategy_used, "output": r.output, "duration_ms": r.duration_ms,
                       "error": r.error, "wave_plan": wave_plan})


@tool(name="run_autonomous", description="Run autonomous developer loop (Plan -> Execute -> Test -> Fix)",
         schema={"type": "object", "properties": {"task": {"type": "string"}, "max_iterations": {"type": "integer", "default": 5}}, "required": ["task"]})
async def _handle_run_autonomous(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.orchestrator.execute_autonomous(arguments.get("task", ""), max_iterations=arguments.get("max_iterations", 5))
    return json.dumps(r)
