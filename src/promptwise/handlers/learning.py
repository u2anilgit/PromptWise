"""handlers.learning -- continuous learning loop MCP tool handlers (moved
verbatim from server.py's "Continuous learning loop (Phase 2)" section
during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="capture_learning", description="Store a correction as a durable, searchable learning (category, mistake, fix, project). Local SQLite + FTS5, offline.",
         schema={"type": "object", "properties": {
             "category": {"type": "string", "description": "e.g. 'style', 'security', 'api-misuse'"},
             "mistake": {"type": "string", "description": "what went wrong"},
             "correction": {"type": "string", "description": "the fix / the rule going forward"},
             "project": {"type": "string", "default": ""},
             "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["category", "mistake", "correction"]})
async def _handle_capture_learning(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.learning_store import LearningStore
    learning = LearningStore().capture(
        category=arguments.get("category", ""), mistake=arguments.get("mistake", ""),
        correction=arguments.get("correction", ""), project=arguments.get("project", ""),
        tags=arguments.get("tags", []))
    return json.dumps({"captured": learning.to_dict()})


@tool(name="replay_learnings", description="Top-K relevant past corrections for a task description (FTS5 BM25, LIKE fallback) plus a ready-to-inject reminder block.",
         schema={"type": "object", "properties": {
             "task": {"type": "string"}, "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 25},
             "project": {"type": "string"}},
         "required": ["task"]})
async def _handle_replay_learnings(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.learning_replay import replay
    return json.dumps(replay(arguments.get("task", ""), k=arguments.get("k", 5),
                             project=arguments.get("project")))


@tool(name="learning_insights", description="Correction trends from the local learning store: counts by category, project, month, and the most-repeated mistakes.",
         schema={"type": "object", "properties": {}})
async def _handle_learning_insights(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.insights import compute_insights
    return json.dumps(compute_insights())


@tool(name="insights_report", description="Ranked, actionable recommendations over local telemetry: routing downgrades/escalations, top cost drivers & spend anomalies, quality/eval regressions, and budget projections. Deterministic, offline, min-sample gated.",
         schema={"type": "object", "properties": {
             "window_days": {"type": "integer", "default": 30, "minimum": 1, "maximum": 365,
                             "description": "analysis window for cost/quality/budget families"},
             "top_n": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100}}})
async def _handle_insights_report(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.insights import compute_recommendations
    recs = compute_recommendations(window_days=arguments.get("window_days", 30))
    top_n = int(arguments.get("top_n", 10))
    return json.dumps({"count": len(recs), "recommendations": recs[:top_n]})
