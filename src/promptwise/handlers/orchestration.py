"""handlers.orchestration -- orchestration MCP tool handlers (moved
verbatim from server.py's "Orchestration" section during the handlers/
package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="orchestrate_tasks", description="Parse a multi-step prompt into a DAG and execute with a failure strategy. Pass 'tasks' (with depends_on / file) to instead emit a safe parallel wave plan (which tasks can run at once) for the caller to dispatch.",
         schema={"type": "object", "properties": {
             "text": {"type": "string"}, "strategy": {"type": "string", "enum": ["stop", "retry", "fallback", "all"], "default": "fallback"},
             "tasks": {"type": "array", "description": "Structured tasks [{id, depends_on:[ids], file}] — when present, returns a wave plan instead of executing",
                       "items": {"type": "object", "properties": {
                           "id": {"type": "string"}, "depends_on": {"type": "array", "items": {"type": "string"}}, "file": {"type": "string"}}}},
             "fan_out_cap": {"type": "integer", "default": 8, "description": "Max tasks per parallel wave"}},
         "required": ["text"]})
async def _handle_orchestrate_tasks(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.task_graph import plan_waves, summarize_plan
    fan_out = int(arguments.get("fan_out_cap", 8))
    tasks_arg = arguments.get("tasks")
    if isinstance(tasks_arg, list) and tasks_arg:
        # emit-not-execute: which tasks are safe to run in parallel
        plan = plan_waves(tasks_arg, fan_out_cap=fan_out)
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
