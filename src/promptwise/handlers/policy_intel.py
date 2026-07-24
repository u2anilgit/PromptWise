"""handlers.policy_intel -- policy intelligence & searchable trace MCP tool
handlers (moved verbatim from server.py's "Policy intelligence &
searchable trace (Phase 4)" section during the handlers/ package split;
see docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="tune_permissions", description="Learn allow/deny permission suggestions from denial telemetry (the Phase 1 PermissionDenied log). Proposals only — never edits config.",
         schema={"type": "object", "properties": {
             "state_dir": {"type": "string", "default": ".", "description": "project dir holding .promptwise/denials.jsonl"},
             "min_count": {"type": "integer", "default": 2, "minimum": 1},
             "mcp_json": {"type": "string", "description": "path to .mcp.json for the current allowlist"}}})
async def _handle_tune_permissions(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.permission_tuner import tune_permissions
    return json.dumps(tune_permissions(
        state_dir=arguments.get("state_dir", "."),
        min_count=arguments.get("min_count", 2),
        mcp_json=arguments.get("mcp_json")))


@tool(name="audit_mcp_servers", description="Audit declared MCP servers (.mcp.json + plugin.json) for security flags, allow-surface, and redundancy. Offline; inspects config, does not call servers.",
         schema={"type": "object", "properties": {
             "repo_root": {"type": "string", "default": "."},
             "extra_configs": {"type": "array", "items": {"type": "string"}}}})
async def _handle_audit_mcp_servers(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.mcp_auditor import audit_mcp_servers
    return json.dumps(audit_mcp_servers(
        repo_root=arguments.get("repo_root", "."),
        extra_configs=arguments.get("extra_configs")))


@tool(name="search_trace", description="Search the trace (hash-chained audit trail + learnings) by meaning. Keyword/FTS by default; optional local embeddings if installed and enabled. Offline.",
         schema={"type": "object", "properties": {
             "query": {"type": "string"}, "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 25},
             "repo_root": {"type": "string", "default": "."},
             "audit_path": {"type": "string"},
             "use_embeddings": {"type": "boolean", "default": False}},
         "required": ["query"]})
async def _handle_search_trace(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.semantic_index import search_trace
    return json.dumps(search_trace(
        arguments.get("query", ""), k=arguments.get("k", 5),
        repo_root=arguments.get("repo_root", "."),
        audit_path=arguments.get("audit_path"),
        use_embeddings=arguments.get("use_embeddings", False)))


@tool(name="rank_context", description="Retrieval-augmented context manager: rank and prune candidates from the trace (audit + learnings) and an optionally-supplied doc onto one token budget. No new ranking algorithm - reuses search_trace's keyword/BM25 (or optional embeddings) scoring; docs are sharded per call, not indexed. Offline.",
         schema={"type": "object", "properties": {
             "query": {"type": "string"},
             "token_budget": {"type": "integer", "default": 2000},
             "doc_path": {"type": "string"},
             "doc_text": {"type": "string"},
             "sources": {"type": "array", "items": {"type": "string", "enum": ["audit", "learnings", "doc"]},
                        "default": ["audit", "learnings", "doc"]},
             "use_embeddings": {"type": "boolean", "default": False},
             "repo_root": {"type": "string", "default": "."},
             "audit_path": {"type": "string"},
             "learning_db": {"type": "string"}},
         "required": ["query"]})
async def _handle_rank_context(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.context_ranker import rank_context
    sources = arguments.get("sources") or ["audit", "learnings", "doc"]
    return json.dumps(rank_context(
        arguments.get("query", ""), token_budget=arguments.get("token_budget", 2000),
        doc_path=arguments.get("doc_path"), doc_text=arguments.get("doc_text"),
        sources=tuple(sources), use_embeddings=arguments.get("use_embeddings", False),
        repo_root=arguments.get("repo_root", "."), audit_path=arguments.get("audit_path"),
        learning_db=arguments.get("learning_db")))


@tool(name="grant_jit_permission", description="Grant a time-boxed permission for a tool signature (e.g. 'Bash:git'), auto-expiring after ttl_minutes (default 60, max 480/8h). Independent of .mcp.json; enforced by the PreToolUse JIT guard hook, which auto-approves while active and falls back to the normal permission prompt once expired. Note: matching is coarse (first command token only, e.g. 'Bash:git' matches any git invocation) -- the same grain permission_tuner's suggestions use; grant narrowly-scoped, short-lived permissions for commands you trust broadly, not ones where the arguments matter.",
         schema={"type": "object", "properties": {
             "signature": {"type": "string", "description": "tool signature, e.g. 'Bash:git' or 'mcp__promptwise__run_governor'"},
             "ttl_minutes": {"type": "integer", "default": 60, "minimum": 1, "maximum": 480}},
         "required": ["signature"]})
async def _handle_grant_jit_permission(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.jit_permissions import JITPermissions
    signature = arguments.get("signature", "")
    ttl_minutes = arguments.get("ttl_minutes", 60)
    rec = JITPermissions().grant(signature, ttl_minutes=ttl_minutes)
    return json.dumps(rec)


@tool(name="revoke_jit_permission", description="Immediately revoke a time-boxed JIT permission grant for a tool signature, before its natural expiry.",
         schema={"type": "object", "properties": {
             "signature": {"type": "string"}},
         "required": ["signature"]})
async def _handle_revoke_jit_permission(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.jit_permissions import JITPermissions
    signature = arguments.get("signature", "")
    JITPermissions().revoke(signature)
    return json.dumps({"signature": signature, "revoked": True})


@tool(name="list_jit_permissions", description="List all JIT permission grants (active and expired) with their expiry timestamps.",
         schema={"type": "object", "properties": {}})
async def _handle_list_jit_permissions(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.jit_permissions import JITPermissions
    grants = JITPermissions().list_all()
    return json.dumps({"grants": grants})
