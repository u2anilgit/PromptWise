"""handlers.compliance_export -- compliance evidence export MCP tool handler
(moved verbatim from server.py's "Compliance evidence export (Phase 7)"
section during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool, _get_audit_log


@tool(name="export_compliance_bundle", description="Build a self-verifying, HMAC-signed compliance evidence bundle from the hash-chained audit trail: verifies the chain, wraps records in a manifest (time range, count, chain-head digest), signs with a local key, and can write a .zip. Offline; no network.",
         schema={"type": "object", "properties": {
             "sign": {"type": "boolean", "default": True, "description": "HMAC-sign the bundle with the local key (env PROMPTWISE_AUDIT_KEY or PROMPTWISE_AUDIT_KEY_FILE)"},
             "control_families": {"type": "array", "items": {"type": "string"}, "description": "generic control-family tags; inferred from the trace when omitted"},
             "out_path": {"type": "string", "description": "optional path to write a .zip evidence archive"}}})
async def _handle_export_compliance_bundle(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.compliance_export import export_bundle
    audit = _get_audit_log()
    records = json.loads(audit.export_json())
    return json.dumps(export_bundle(
        records, sign=arguments.get("sign", True),
        control_families=arguments.get("control_families"),
        out_path=arguments.get("out_path")))
