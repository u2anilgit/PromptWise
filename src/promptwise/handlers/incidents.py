"""handlers.incidents -- incident response & forensics MCP tool handlers
(WP3). New category, no pre-split ordering to preserve -- see
core/incidents.py, core/playbooks.py, core/aivss.py (shared with WP2).
"""
from __future__ import annotations

import json
import logging

from promptwise.core.tool_registry import ServerContext, tool, _get_audit_log

_logger = logging.getLogger(__name__)


@tool(name="create_incident", description="Open a new incident (status starts 'open'). Optional metadata dict can link back to a triggering source, e.g. a WP2 anomaly finding.",
         schema={"type": "object", "properties": {
             "title": {"type": "string"}, "description": {"type": "string", "default": ""},
             "severity": {"type": "string", "default": "unknown"},
             "metadata": {"type": "object", "default": {}}},
         "required": ["title"]})
async def _handle_create_incident(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.incidents import IncidentStore
    inc = IncidentStore().create(
        arguments.get("title", ""), description=arguments.get("description", ""),
        severity=arguments.get("severity", "unknown"), metadata=arguments.get("metadata", {}))

    # WP4: tag the new incident with any matching threat-intel context.
    # Fail-soft -- a broken/missing intel store must never block incident
    # creation (matches the project's fail-open/fail-soft detector rule).
    intel_matches: list = []
    try:
        from promptwise.security.threat_intel import ThreatIntelStore, correlate
        intel_matches = correlate(
            ThreatIntelStore(),
            content=f"{arguments.get('title', '')} {arguments.get('description', '')}",
            incident_id=inc.id)
    except Exception as e:
        try:
            _logger.debug("threat-intel correlation failed: %s", e)
        except Exception:
            pass

    out = inc.to_dict()
    out["intel_matches"] = intel_matches
    return json.dumps(out)


@tool(name="list_incidents", description="List incidents, optionally filtered by status (open/triaged/contained/resolved/closed).",
         schema={"type": "object", "properties": {"status": {"type": "string"}}})
async def _handle_list_incidents(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.incidents import IncidentStore
    incidents = IncidentStore().list_all(status=arguments.get("status"))
    return json.dumps({"incidents": [i.to_dict() for i in incidents]})


@tool(name="update_incident", description="Advance an incident's status along the enforced lifecycle (open->triaged->contained->resolved->closed, linear only, no skipping). Returns an error object (not a raised exception) on an illegal transition.",
         schema={"type": "object", "properties": {
             "incident_id": {"type": "integer"}, "status": {"type": "string"},
             "actor": {"type": "string", "default": ""}},
         "required": ["incident_id", "status"]})
async def _handle_update_incident(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.incidents import IncidentStore
    try:
        inc = IncidentStore().update_status(
            int(arguments.get("incident_id", -1)), arguments.get("status", ""),
            actor=arguments.get("actor", ""))
    except ValueError as e:
        return json.dumps({"error": str(e), "type": "IllegalTransition"})
    return json.dumps(inc.to_dict())


@tool(name="close_incident", description="Close a 'resolved' incident and auto-capture a learning (mistake/correction) into the learning store. Requires the incident to already be in 'resolved' status -- returns an error object otherwise.",
         schema={"type": "object", "properties": {
             "incident_id": {"type": "integer"}, "actor": {"type": "string", "default": ""},
             "mistake": {"type": "string"}, "correction": {"type": "string"},
             "project": {"type": "string", "default": ""}, "tags": {"type": "array", "items": {"type": "string"}, "default": []}},
         "required": ["incident_id", "mistake", "correction"]})
async def _handle_close_incident(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.incidents import IncidentStore
    from promptwise.core.learning_store import LearningStore
    try:
        inc = IncidentStore().update_status(
            int(arguments.get("incident_id", -1)), "closed", actor=arguments.get("actor", ""))
    except ValueError as e:
        return json.dumps({"error": str(e), "type": "IllegalTransition"})
    LearningStore().capture(
        category="incident", mistake=arguments.get("mistake", ""),
        correction=arguments.get("correction", ""), project=arguments.get("project", ""),
        tags=arguments.get("tags", []))
    out = inc.to_dict()
    out["learning_captured"] = True
    return json.dumps(out)


@tool(name="score_incident", description="Score an incident's severity 0-100 using the AIVSS v0.5 agentic-dimensions rubric (core/aivss.py, shared with the behavioral-anomaly-detection feature) and persist the score onto the incident record.",
         schema={"type": "object", "properties": {
             "incident_id": {"type": "integer"},
             "factors": {"type": "object", "description": "0-100 raw sub-scores for autonomy/tool_access/memory_persistence/multi_agent_reach; missing keys default to 0"}},
         "required": ["incident_id", "factors"]})
async def _handle_score_incident(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.aivss import score
    from promptwise.core.incidents import IncidentStore
    result = score(arguments.get("factors", {}))
    try:
        inc = IncidentStore().set_score(int(arguments.get("incident_id", -1)), result.total)
    except ValueError as e:
        return json.dumps({"error": str(e), "type": "UnknownIncident"})
    out = inc.to_dict()
    out["aivss_breakdown"] = result.breakdown
    return json.dumps(out)


@tool(name="incident_timeline", description="Reconstruct a chronological timeline for an incident: its own recorded events (from create_incident/update_incident/close_incident) merged with matching hash-chained audit records (filtered by correlation_key, a substring matched against each audit record's task/rules_applied/compliance_decision). This is the forensic payoff of the tamper-evident audit design -- the timeline can't have been quietly edited after the fact.",
         schema={"type": "object", "properties": {
             "incident_id": {"type": "integer"},
             "correlation_key": {"type": "string", "description": "substring to match against the audit trail, e.g. an actor name or a rules_applied entry"}},
         "required": ["incident_id", "correlation_key"]})
async def _handle_incident_timeline(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.incidents import IncidentStore
    incident_id = int(arguments.get("incident_id", -1))
    inc = IncidentStore().get(incident_id)
    if inc is None:
        return json.dumps({"error": f"no incident with id {incident_id}", "type": "UnknownIncident"})

    events = IncidentStore().list_events(incident_id)
    timeline = [{"source": "incident_event", "ts": e.ts, **e.to_dict()} for e in events]

    audit_records = _get_audit_log().query(contains=arguments.get("correlation_key", ""))
    for rec in audit_records:
        timeline.append({"source": "audit", "ts": rec.get("timestamp", ""), **rec})

    timeline.sort(key=lambda e: e.get("ts", ""))
    return json.dumps({"incident_id": incident_id, "timeline": timeline})


def _regulatory_sections(inc, events: list) -> dict:
    """Build the NIS2/GDPR/EU AI Act sections for an incident bundle manifest.

    Anti-fabrication discipline (matches security/framework_map.py:9-16):
    a field is populated ONLY when the incident record genuinely carries
    the underlying data. A field with no evidenced source is OMITTED from
    the dict entirely -- never filled with None/"unknown"/a guessed value.
    This is the same discipline core/sbom.py's AI-BOM emitter and
    security/framework_map.py's OWASP/NIST/MITRE category mapping already
    established in this codebase; this plan (docs/superpowers/plans/
    2026-08-18-wp3-incident-response.md) is the source for these three
    incident-specific field mappings, since they aren't external framework
    category lookups the way framework_map.py's are.
    """
    nis2: dict = {}
    gdpr: dict = {}
    eu_ai_act: dict = {}

    if inc.created_at:
        nis2["detected_at"] = inc.created_at
        gdpr["detected_at"] = inc.created_at
        eu_ai_act["detected_at"] = inc.created_at
    if inc.severity and inc.severity != "unknown":
        nis2["severity"] = inc.severity
        eu_ai_act["severity"] = inc.severity
    if inc.aivss_score is not None:
        eu_ai_act["aivss_score"] = inc.aivss_score
    if inc.title:
        nis2["incident_title"] = inc.title
        gdpr["incident_title"] = inc.title
        eu_ai_act["incident_title"] = inc.title
    contained_events = [e for e in events if e.event_type == "status_change" and "contained" in e.detail]
    if contained_events:
        nis2["contained_at"] = contained_events[0].ts
    resolved_events = [e for e in events if e.event_type == "status_change" and "resolved" in e.detail]
    if resolved_events:
        gdpr["resolved_at"] = resolved_events[0].ts

    return {"nis2": nis2, "gdpr": gdpr, "eu_ai_act": eu_ai_act}


@tool(name="export_incident_bundle", description="Export a signed (Ed25519) forensic bundle for an incident: the incident record, its events, correlated audit-trail records, and three regulatory-regime sections (NIS2 24h early-warning, GDPR 72h Art.33, EU AI Act Art.73 serious-incident fields) populated only from data the incident genuinely carries -- unavailable fields are omitted, never guessed. Reuses the exact Ed25519 sign+zip pipeline compliance bundles already use.",
         schema={"type": "object", "properties": {
             "incident_id": {"type": "integer"},
             "correlation_key": {"type": "string", "description": "substring to match against the audit trail for this incident"}},
         "required": ["incident_id", "correlation_key"]})
async def _handle_export_incident_bundle(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.compliance_export import build_bundle, sign_bundle_ed25519
    from promptwise.core.incidents import IncidentStore

    incident_id = int(arguments.get("incident_id", -1))
    store = IncidentStore()
    inc = store.get(incident_id)
    if inc is None:
        return json.dumps({"error": f"no incident with id {incident_id}", "type": "UnknownIncident"})

    events = store.list_events(incident_id)
    audit_records = _get_audit_log().query(contains=arguments.get("correlation_key", ""))

    bundle = build_bundle(audit_records)
    bundle["manifest"].update(_regulatory_sections(inc, events))
    bundle["manifest"]["incident"] = inc.to_dict()
    bundle["manifest"]["incident_events"] = [e.to_dict() for e in events]

    signed = sign_bundle_ed25519(bundle)
    return json.dumps(signed)


@tool(name="run_playbook", description="Load and run a YAML incident-response playbook (dry-run by default -- 'advise' mode, which reports what WOULD happen and changes nothing). Set mode='apply' (or the PROMPTWISE_AUTONOMY=apply env var) to actually execute steps -- same autonomy-gating posture as run_governor. Starter playbooks ship under config/playbooks/.",
         schema={"type": "object", "properties": {
             "path": {"type": "string", "description": "path to a playbook YAML file, e.g. config/playbooks/prompt_injection_confirmed.yaml"},
             "mode": {"type": "string", "enum": ["advise", "dry_run", "apply"], "description": "overrides PROMPTWISE_AUTONOMY for this call; omit to use the env var (default advise)"}},
         "required": ["path"]})
async def _handle_run_playbook(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.playbooks import load_playbook, run_playbook
    try:
        pb = load_playbook(arguments.get("path", ""))
    except (FileNotFoundError, OSError) as e:
        return json.dumps({"error": str(e), "type": "PlaybookNotFound"})
    run = run_playbook(pb, mode=arguments.get("mode"))
    return json.dumps(run.to_dict())
