"""handlers.roi -- ROI/cost-reporting MCP tool handlers (moved verbatim
from server.py's "ROI" section during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.session_context import CURRENT_SESSION_ID
from promptwise.core.tool_registry import ServerContext, tool


@tool(name="session_cost_report", description="Per-session cost rollup: calls, cost, tokens, and tool breakdown grouped by session_id. Defaults to just the current session (current_session_only=true) -- 'what has this session cost so far'; set false to see the full multi-session breakdown. A process gets a real, distinct session_id at startup, so this is meaningful per Claude Code session, not one global bucket.",
         schema={"type": "object", "properties": {"since": {"type": "string", "description": "ISO-8601 cutoff; omit for all history"}, "current_session_only": {"type": "boolean", "default": True}}})
async def _handle_session_cost_report(ctx: ServerContext, arguments: dict) -> str:
    rows = await ctx.memory.session_cost_report(since=arguments.get("since"))
    if arguments.get("current_session_only", True):
        rows = [r for r in rows if r["session_id"] == CURRENT_SESSION_ID]
    return json.dumps({"current_session_id": CURRENT_SESSION_ID, "sessions": rows})


@tool(name="track_roi", description="Calculate ROI ratio: value of time saved vs cost incurred",
         schema={"type": "object", "properties": {
             "session_id": {"type": "string"}, "total_cost_usd": {"type": "number"}, "tokens_saved": {"type": "integer"}, "calls": {"type": "integer"}},
         "required": ["session_id", "total_cost_usd", "tokens_saved", "calls"]})
async def _handle_track_roi(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.roi.calculate(session_id=arguments.get("session_id", ""), total_cost_usd=float(arguments.get("total_cost_usd", 0)),
                          tokens_saved=int(arguments.get("tokens_saved", 0)), calls=int(arguments.get("calls", 1)))
    # NOTE: calculate() only returns a snapshot, it never persisted — roi_stats
    # stayed empty forever regardless of how many times this tool was called.
    # Persist so cost_report / get_roi_report have something to read.
    try:
        await ctx.memory.log_roi_stat(developer="Anonymous", role="Dev", tokens_saved=r.tokens_saved,
                                      cost_usd=r.total_cost_usd, hours_saved=round(r.estimated_time_saved_min / 60, 4))
    except Exception:
        pass  # never fail the tool call over a persistence hiccup
    return json.dumps({"roi_ratio": r.roi_ratio, "estimated_time_saved_min": r.estimated_time_saved_min,
                       "productivity_score": r.productivity_score, "total_cost_usd": r.total_cost_usd})


@tool(name="get_roi_report", description="Generate team ROI report based on cumulative stats",
         schema={"type": "object", "properties": {"period": {"type": "string", "enum": ["daily", "weekly", "monthly"], "default": "weekly"}}})
async def _handle_get_roi_report(ctx: ServerContext, arguments: dict) -> str:
    stats = await ctx.memory.get_roi_stats(period=arguments.get("period", "weekly"))
    total_hours = sum(s["hours_saved"] for s in stats)
    total_cost = sum(s["cost_usd"] for s in stats)
    total_tokens = sum(s["tokens_saved"] for s in stats)
    return json.dumps({"period": arguments.get("period", "weekly"), "total_hours_saved": round(total_hours, 2),
                       "total_cost_usd": round(total_cost, 6), "total_tokens_saved": total_tokens, "records": stats})


@tool(name="cost_report", description="Get cost breakdown by project/period",
         schema={"type": "object", "properties": {"project_id": {"type": "string"}, "period": {"type": "string", "default": "weekly"}, "format": {"type": "string", "enum": ["json", "otlp"], "default": "json", "description": "otlp emits an OpenTelemetry GenAI semantic-convention OTLP-JSON resourceMetrics payload instead of the plain report"}}})
async def _handle_cost_report(ctx: ServerContext, arguments: dict) -> str:
    stats = await ctx.memory.get_roi_stats(period=arguments.get("period", "weekly"))
    pid = arguments.get("project_id")
    if pid:
        stats = [s for s in stats if s.get("project_id") == pid]
    by_skill = {}
    for s in stats:
        sk = s.get("skill", "unknown")
        by_skill.setdefault(sk, {"cost_usd": 0.0, "calls": 0})
        by_skill[sk]["cost_usd"] += s.get("cost_usd", 0.0)
        by_skill[sk]["calls"] += 1
    report = {"period": arguments.get("period", "weekly"), "project_id": pid,
             "total_cost_usd": round(sum(v["cost_usd"] for v in by_skill.values()), 6), "by_skill": by_skill}
    if arguments.get("format") == "otlp":
        from promptwise.core.otel_exporter import cost_report_to_otlp_metrics
        return json.dumps(cost_report_to_otlp_metrics(report))
    return json.dumps(report)
