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


@tool(name="check_routing_consent", description="Check whether the assistant has device-scoped, ask-once consent for a routing question (e.g. key='opus' for 'use Opus for this?'). Device-scoped (~/.promptwise), not project-scoped -- persists across all projects on this machine. Purely advisory bookkeeping for the assistant's own behavior; has zero effect on Router.route()'s actual tier selection.",
         schema={"type": "object", "properties": {"key": {"type": "string", "default": "opus"}}})
async def _handle_check_routing_consent(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.routing_consent import RoutingConsent
    key = arguments.get("key") or "opus"
    granted = RoutingConsent().is_granted(key)
    return json.dumps({"key": key, "granted": granted})


@tool(name="grant_routing_consent", description="Record device-scoped, ask-once consent for a routing question (e.g. key='opus') so the assistant never asks again on this device. Call this after the user explicitly says yes. Purely advisory bookkeeping; has zero effect on Router.route()'s actual tier selection.",
         schema={"type": "object", "properties": {"key": {"type": "string", "default": "opus"}}})
async def _handle_grant_routing_consent(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.routing_consent import RoutingConsent
    key = arguments.get("key") or "opus"
    RoutingConsent().grant(key)
    return json.dumps({"key": key, "granted": True})


class BudgetExceededError(Exception):
    """Raised by monitor_budget only when BudgetGuardian is in opt-in
    "block" mode and spend has crossed the hard limit. Surfaced as an
    error-typed JSON response carrying the full BudgetStatus so callers can
    distinguish a real hard block from an ordinary tool failure."""

    def __init__(self, status):
        self.status = status
        super().__init__(f"budget hard limit exceeded: {status.used_usd} >= {status.limit_usd}")


@tool(name="monitor_budget", description="Check spend against budget limit",
         schema={"type": "object", "properties": {
             "used_usd": {"type": "number"}, "days_elapsed": {"type": "integer", "default": 1}, "project_id": {"type": "string"},
             "tool_cost_usd": {"type": "number", "description": "Tool/API execution cost for this workflow, attributed alongside used_usd's LLM token cost"}},
         "required": ["used_usd"]})
async def _handle_monitor_budget(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.budget.check(used_usd=float(arguments.get("used_usd", 0)), days_elapsed=int(arguments.get("days_elapsed", 1)),
                         project_id=arguments.get("project_id"), tool_cost_usd=float(arguments.get("tool_cost_usd", 0) or 0))
    _maybe_alert_budget(r)
    if r.blocked:
        # Opt-in hard-blocking mode only (BudgetGuardian.mode == "block", set via
        # set_budget_limit(..., mode="block")). Surfacing an error-typed
        # response (rather than just alert_level="hard_stop" in an ordinary
        # payload) is what makes this a real hard block callers must handle,
        # not a warning that's easy to ignore.
        err = BudgetExceededError(r)
        return json.dumps({"error": str(err), "type": type(err).__name__, "tool": "monitor_budget",
                           "blocked": True, "used_usd": r.used_usd, "limit_usd": r.limit_usd})
    return json.dumps({"used_usd": r.used_usd, "limit_usd": r.limit_usd, "pct_used": r.pct_used,
                       "daily_burn_usd": r.daily_burn_usd, "projected_monthly_usd": r.projected_monthly_usd,
                       "alert_level": r.alert_level, "project_id": r.project_id, "cost_breakdown": r.cost_breakdown,
                       "blocked": r.blocked})


@tool(name="predict_cost", description="Estimate cost of a prompt before sending",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "model": {"type": "string", "default": "claude-sonnet-4-6"}}, "required": ["prompt"]})
async def _handle_predict_cost(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.budget.predict_cost(arguments.get("prompt", ""), model=arguments.get("model", "claude-sonnet-4-6"))
    return json.dumps(r)


@tool(name="set_budget_limit", description="Set monthly or daily spending limit; optionally switch the guardian between advisory (default) and opt-in hard-blocking enforcement",
         schema={"type": "object", "properties": {
             "limit_usd": {"type": "number"}, "period": {"type": "string", "enum": ["daily", "monthly"], "default": "monthly"},
             "mode": {"type": "string", "enum": ["advise", "block"], "description": "advise (default) never blocks; block hard-stops monitor_budget once spend crosses the limit. Opt-in only."}},
         "required": ["limit_usd"]})
async def _handle_set_budget_limit(ctx: ServerContext, arguments: dict) -> str:
    ctx.budget.set_limit(float(arguments.get("limit_usd", 0)), period=arguments.get("period", "monthly"))
    if "mode" in arguments:
        ctx.budget.set_mode(arguments["mode"])
    return json.dumps({"status": "ok", "limit_usd": arguments.get("limit_usd"),
                       "period": arguments.get("period", "monthly"), "mode": ctx.budget.mode})


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
