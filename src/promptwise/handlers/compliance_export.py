"""handlers.compliance_export -- compliance evidence export MCP tool handler
(moved verbatim from server.py's "Compliance evidence export (Phase 7)"
section during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool, _get_audit_log


@tool(name="export_compliance_bundle", description="Build a self-verifying, signed compliance evidence bundle from the hash-chained audit trail: verifies the chain, wraps records in a manifest (time range, count, chain-head digest), signs with a local key, and can write a .zip. Offline; no network.",
         schema={"type": "object", "properties": {
             "sign": {"type": "boolean", "default": True, "description": "sign the bundle with the local key (env PROMPTWISE_AUDIT_KEY/PROMPTWISE_AUDIT_KEY_FILE for hmac, PROMPTWISE_ED25519_KEY/PROMPTWISE_ED25519_KEY_FILE for ed25519)"},
             "sign_alg": {"type": "string", "enum": ["hmac", "ed25519"], "default": "hmac", "description": "hmac (shared-secret, default) or ed25519 (asymmetric, verifiable by a third party without the private key)"},
             "control_families": {"type": "array", "items": {"type": "string"}, "description": "generic control-family tags; inferred from the trace when omitted"},
             "out_path": {"type": "string", "description": "optional path to write a .zip evidence archive"}}})
async def _handle_export_compliance_bundle(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.compliance_export import export_bundle
    audit = _get_audit_log()
    records = json.loads(audit.export_json())
    return json.dumps(export_bundle(
        records, sign=arguments.get("sign", True),
        sign_alg=arguments.get("sign_alg", "hmac"),
        control_families=arguments.get("control_families"),
        out_path=arguments.get("out_path")))


@tool(name="generate_ed25519_keypair", description="Generate a fresh Ed25519 keypair for compliance bundle signing. Returned in-memory only -- never written to disk. Store the private_key yourself (e.g. as PROMPTWISE_ED25519_KEY) before it is lost; share the public_key with auditors who need to verify bundles you sign. Note: a bundle verifying with signature_ok=True only proves internal self-consistency (signed by *some* keypair), not authenticity -- auditors must compare the bundle's embedded public_key against the public_key you shared with them out-of-band.",
         schema={"type": "object", "properties": {}})
async def _handle_generate_ed25519_keypair(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.compliance_export import generate_ed25519_keypair
    return json.dumps(generate_ed25519_keypair())


@tool(name="compliance_gap_analysis", description="Per-framework required-control checklist vs controls evidenced by this server's actually-registered tools: implemented / partial / absent, with the evidencing tool names. Frameworks: owasp_agentic_top10 (ASI01-10), owasp_nhi_top10, csa_aicm (4 genuinely-evidenced domains only), gdpr (Arts. 5/25/32/33), hipaa (164.312 a-e). Advisory starting point, not a certification.",
         schema={"type": "object", "properties": {
             "framework": {"type": "string", "enum": ["owasp_agentic_top10", "owasp_nhi_top10", "csa_aicm", "gdpr", "hipaa"]}},
         "required": ["framework"]})
async def _handle_compliance_gap_analysis(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.security.framework_map import gap_analysis
    try:
        from promptwise.server import _TOOL_DEFS
        registered_tools = [t.name for t in _TOOL_DEFS]
    except Exception:
        registered_tools = []
    return json.dumps(gap_analysis(arguments.get("framework", ""), registered_tools))
