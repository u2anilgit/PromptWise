"""handlers.detection -- behavioral anomaly detection MCP tool handlers
(WP2). New category, no pre-split ordering to preserve -- see
core/behavior_baseline.py, core/anomaly_detector.py, core/siem_emit.py.
"""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool, _get_audit_log


@tool(name="baseline_behavior", description="Build and persist a per-actor statistical behavior baseline (prompt-length median/MAD, tool-call bigram frequencies, model-tier mix, hourly activity histogram, distinct files touched) from telemetry already collected in cost_logs and the audit trail. Pure stdlib stats, no ML. Caveat: when cost_logs/audit_records are omitted (live-fetch path), only distinct_files_touched is genuinely actor-scoped -- cost_logs rows carry no actor field, so the other four metrics reflect ALL actors' cost_logs within the window, not just the named actor.",
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
    cost_logs = arguments.get("cost_logs")
    if cost_logs is None:
        # compute_baseline()'s own live-fetch fallback uses asyncio.run(), which
        # cannot run inside this already-running async MCP event loop -- so we
        # pre-fetch here (with the same since-window logic) and always pass
        # cost_logs explicitly, keeping compute_baseline's asyncio.run() branch
        # unreached from async context. See core/behavior_baseline.py.
        from promptwise.db.models import MemoryManager, get_db_path
        since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - window_days * 86400))
        cost_logs = await MemoryManager(str(get_db_path())).raw_cost_logs(since=since)
    stats = compute_baseline(
        actor, window_days=window_days,
        cost_logs=cost_logs, audit_records=arguments.get("audit_records"))
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
    window_dict = dict(arguments.get("window", {}))
    window_dict.setdefault("actor", actor)
    window_dict.setdefault("window_days", 30)
    window = BehaviorStats(**window_dict)
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


@tool(name="emit_siem", description="Map an anomaly finding or audit record to an OCSF class dict and emit it -- file-drop (default, .promptwise/siem/) or webhook (reuses the existing WebhookSink). No SDKs, dict mapping + json formatting only.",
         schema={"type": "object", "properties": {
             "record": {"type": "object", "description": "an AnomalyFinding.to_dict() or a raw audit record dict"},
             "mode": {"type": "string", "enum": ["file", "webhook"], "default": "file"},
             "drop_dir": {"type": "string", "default": ".promptwise/siem/"},
             "webhook_url": {"type": "string"}},
         "required": ["record"]})
async def _handle_emit_siem(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.siem_emit import SiemEmitter
    emitter = SiemEmitter(
        mode=arguments.get("mode", "file"), drop_dir=arguments.get("drop_dir", ".promptwise/siem/"),
        webhook_url=arguments.get("webhook_url"))
    return json.dumps(emitter.emit(arguments.get("record", {})))
