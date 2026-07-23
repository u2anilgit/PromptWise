"""handlers.budget_cost -- budget & cost MCP tool handlers (moved verbatim
from server.py's "Budget & Cost" section during the handlers/ package
split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

from promptwise.core.tool_registry import ServerContext, tool


def _maybe_alert_budget(status) -> None:
    """Best-effort, opt-in notification hook (Phase 16). Subscribes to an
    ALREADY-COMPUTED BudgetStatus; never touches plugins/budget.py."""
    try:
        from promptwise.core import alerts
        alerts.notify_budget(status)
    except Exception:
        pass


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
