"""handlers.intel -- threat intelligence MCP tool handlers (WP4). New
category, no pre-split ordering to preserve -- see security/threat_intel.py.
"""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool, _get_audit_log


@tool(name="import_threat_feed", description="Parse and import a local STIX 2.1 bundle file (indicator/attack-pattern/intrusion-set/relationship objects only -- other types are skipped, not errored) into the threat-intel store, deduped by STIX id. allow_network=True is a documented forward-compat seam for TAXII 2.1 polling and is NOT implemented -- it raises NotImplementedError today; the default (offline, file-based) path is what's supported.",
         schema={"type": "object", "properties": {
             "bundle_path": {"type": "string"}, "source": {"type": "string", "default": ""},
             "allow_network": {"type": "boolean", "default": False}},
         "required": ["bundle_path"]})
async def _handle_import_threat_feed(ctx: ServerContext, arguments: dict) -> str:
    if arguments.get("allow_network"):
        return json.dumps({
            "error": "TAXII 2.1 network ingestion is not implemented -- import a local STIX bundle file instead.",
            "type": "NotImplementedError",
        })
    from promptwise.security.threat_intel import import_bundle_file
    try:
        result = import_bundle_file(arguments.get("bundle_path", ""), source=arguments.get("source", ""))
    except FileNotFoundError as e:
        return json.dumps({"error": str(e), "type": "FileNotFoundError"})
    except json.JSONDecodeError as e:
        return json.dumps({"error": str(e), "type": "JSONDecodeError"})
    return json.dumps(result)


@tool(name="correlate_threats", description="Join content and/or a list of MITRE ATLAS technique IDs against the imported threat-intel store (ATLAS-ID match + indicator string match). Writes intel_matches rows when audit_record_id or incident_id is given; a dry probe with neither is not persisted. Called automatically (fail-soft) by create_incident -- also callable standalone for backfill.",
         schema={"type": "object", "properties": {
             "content": {"type": "string", "default": ""},
             "atlas_technique_ids": {"type": "array", "items": {"type": "string"}, "default": []},
             "audit_record_id": {"type": "string", "default": ""},
             "incident_id": {"type": "integer", "default": 0}}})
async def _handle_correlate_threats(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.security.threat_intel import ThreatIntelStore, correlate
    matches = correlate(
        ThreatIntelStore(), content=arguments.get("content", ""),
        atlas_technique_ids=arguments.get("atlas_technique_ids", []),
        audit_record_id=arguments.get("audit_record_id", ""),
        incident_id=int(arguments.get("incident_id", 0) or 0))
    return json.dumps({"matches": matches})


@tool(name="enrich_audit", description="Append a read-only threat-intel enrichment annotation to the audit trail for a record's already-recorded intel matches (see correlate_threats). Never mutates the hash chain -- the enrichment is a new audit record, same as every other audit append in this codebase.",
         schema={"type": "object", "properties": {"audit_record_id": {"type": "string"}}, "required": ["audit_record_id"]})
async def _handle_enrich_audit(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.security.threat_intel import ThreatIntelStore, enrich_audit
    result = enrich_audit(ThreatIntelStore(), _get_audit_log(), arguments.get("audit_record_id", ""))
    return json.dumps(result)


@tool(name="export_indicators", description="Export imported indicator objects (PII-scrubbed) for sharing back to a SOC/SIEM. Returns data for the caller to send -- makes no network call itself.",
         schema={"type": "object", "properties": {"format": {"type": "string", "default": "json"}}})
async def _handle_export_indicators(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.security.threat_intel import ThreatIntelStore, export_indicators
    try:
        return export_indicators(ThreatIntelStore(), fmt=arguments.get("format", "json"))
    except ValueError as e:
        return json.dumps({"error": str(e), "type": "UnsupportedFormat"})
