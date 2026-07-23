"""handlers.prompt_registry -- versioned prompt registry MCP tool handlers
(moved verbatim from server.py's "Prompt Registry" section during the
handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import difflib
import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="save_prompt", description="Save a prompt to the versioned prompt registry",
         schema={"type": "object", "properties": {"name": {"type": "string"}, "content": {"type": "string"}, "version": {"type": "string", "default": "1.0.0"}, "description": {"type": "string", "default": ""}, "tags": {"type": "array", "items": {"type": "string"}, "default": []}}, "required": ["name", "content"]})
async def _handle_save_prompt(ctx: ServerContext, arguments: dict) -> str:
    await ctx.memory.save_prompt(arguments.get("name", ""), arguments.get("content", ""), arguments.get("version", "1.0.0"),
                                  arguments.get("description", ""), arguments.get("tags", []))
    return json.dumps({"status": "saved", "name": arguments.get("name"), "version": arguments.get("version", "1.0.0")})


@tool(name="search_prompts", description="Search prompts in the versioned prompt registry",
         schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})
async def _handle_search_prompts(ctx: ServerContext, arguments: dict) -> str:
    prompts = await ctx.memory.search_prompts(arguments.get("query", ""))
    return json.dumps({"prompts": prompts})


@tool(name="compare_prompts", description="Diff two versions of a registered prompt",
         schema={"type": "object", "properties": {"name": {"type": "string"}, "version_a": {"type": "string"}, "version_b": {"type": "string"}}, "required": ["name", "version_a", "version_b"]})
async def _handle_compare_prompts(ctx: ServerContext, arguments: dict) -> str:
    name_val = arguments.get("name", "")
    va, vb = arguments.get("version_a"), arguments.get("version_b")
    all_p = await ctx.memory.search_prompts(name_val)
    exact = [p for p in all_p if p["name"] == name_val]
    pa = next((p for p in exact if p["version"] == va), None)
    pb = next((p for p in exact if p["version"] == vb), None)
    if not pa: return json.dumps({"error": f"Version {va} not found"})
    if not pb: return json.dumps({"error": f"Version {vb} not found"})
    diff = "".join(difflib.unified_diff(pa["content"].splitlines(keepends=True), pb["content"].splitlines(keepends=True),
                                         fromfile=f"{name_val}@{va}", tofile=f"{name_val}@{vb}")) or "(no difference)"
    return json.dumps({"version_a": va, "version_b": vb, "token_delta": len(pb["content"])//4 - len(pa["content"])//4, "diff": diff})
