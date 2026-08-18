"""handlers.detection -- behavioral anomaly detection MCP tool handlers
(WP2). New category, no pre-split ordering to preserve -- see
core/behavior_baseline.py, core/anomaly_detector.py, core/siem_emit.py.
"""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="baseline_behavior", description="Build and persist a per-actor statistical behavior baseline (prompt-length median/MAD, tool-call bigram frequencies, model-tier mix, hourly activity histogram, distinct files touched) from telemetry already collected in cost_logs and the audit trail. Pure stdlib stats, no ML.",
         schema={"type": "object", "properties": {
             "actor": {"type": "string"}, "window_days": {"type": "integer", "default": 30},
             "cost_logs": {"type": "array", "items": {"type": "object"}, "description": "optional pre-fetched cost_logs rows; omit to fetch live"},
             "audit_records": {"type": "array", "items": {"type": "object"}, "description": "optional pre-fetched audit records; omit to fetch live"}},
         "required": ["actor"]})
async def _handle_baseline_behavior(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.behavior_baseline import BaselineStore, compute_baseline
    import time
    actor = arguments.get("actor", "")
    window_days = arguments.get("window_days", 30)
    stats = compute_baseline(
        actor, window_days=window_days,
        cost_logs=arguments.get("cost_logs"), audit_records=arguments.get("audit_records"))
    computed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    BaselineStore().save(actor, "behavior", window_days, stats.to_dict(), computed_at)
    out = stats.to_dict()
    out["computed_at"] = computed_at
    out["saved"] = True
    return json.dumps(out)
