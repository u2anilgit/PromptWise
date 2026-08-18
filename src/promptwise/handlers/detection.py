"""handlers.detection -- behavioral anomaly detection MCP tool handlers
(WP2). New category, no pre-split ordering to preserve -- see
core/behavior_baseline.py, core/anomaly_detector.py, core/siem_emit.py.
"""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool, _get_audit_log


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


@tool(name="detect_anomalies", description="Compare a behavior window against a stored baseline (see baseline_behavior) and return AIVSS-scored anomaly findings: off-distribution volume/tempo, never-seen-before tool sequences (recon/exfil-pattern-aware), and data-scope expansion. Advisory only -- appends every finding to the audit trail and does not block anything.",
         schema={"type": "object", "properties": {
             "actor": {"type": "string"},
             "window": {"type": "object", "description": "a BehaviorStats dict, e.g. from baseline_behavior computed over a short recent window"},
             "baseline": {"type": "object", "description": "a stored BehaviorStats dict to compare against; omit to load the most recent saved baseline for actor"},
             "mad_threshold": {"type": "number", "default": 3.0}},
         "required": ["actor", "window"]})
async def _handle_detect_anomalies(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.anomaly_detector import detect_anomalies
    from promptwise.core.behavior_baseline import BaselineStore, BehaviorStats
    from promptwise.core.alerts import notify_anomaly

    actor = arguments.get("actor", "")
    window = BehaviorStats(**arguments.get("window", {}))
    baseline_arg = arguments.get("baseline")
    if baseline_arg is not None:
        baseline = BehaviorStats(**baseline_arg)
    else:
        stored = BaselineStore().load(actor, "behavior", 30)
        baseline = BehaviorStats(**stored["stats_json"]) if stored else BehaviorStats(actor=actor, window_days=30)

    findings = detect_anomalies(actor, window=window, baseline=baseline,
                                 mad_threshold=arguments.get("mad_threshold", 3.0))
    audit = _get_audit_log()
    for f in findings:
        d = f.to_dict()
        audit.append("anomaly_detected", actor=actor, rules_applied=[f.category],
                      files_touched=[], gate_decision="", compliance_decision="n/a")
        notify_anomaly(d)
    return json.dumps({"actor": actor, "findings": [f.to_dict() for f in findings]})
