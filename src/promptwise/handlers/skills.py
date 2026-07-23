"""handlers.skills -- skill invocation MCP tool handlers (moved verbatim
from server.py's "Skills" section during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool, _record_skill_execution


@tool(name="invoke_skill", description="Invoke a specific skill with context",
         schema={"type": "object", "properties": {"skill_name": {"type": "string"}, "context": {"type": "object", "default": {}}, "params": {"type": "object", "default": {}}}, "required": ["skill_name"]})
async def _handle_invoke_skill(ctx: ServerContext, arguments: dict) -> str:
    sk = ctx.skill_loader.get_skill(arguments.get("skill_name", ""))
    if not sk:
        return json.dumps({"error": "Skill not found", "skill_name": arguments.get("skill_name")})
    res = await ctx.orchestrator.execute_skill(sk, arguments.get("context", {}), router=ctx.router)
    await _record_skill_execution(ctx, tool="invoke_skill", skill_name=sk.name, result=res)
    return json.dumps(res)


@tool(name="list_skills", description="List all available skills filtered by role",
         schema={"type": "object", "properties": {"role": {"type": "string"}, "category": {"type": "string"}}})
async def _handle_list_skills(ctx: ServerContext, arguments: dict) -> str:
    skills_list = []
    for sk in ctx.skill_loader.skills.values():
        role_filter = arguments.get("role")
        if role_filter and sk.roles and role_filter not in sk.roles:
            continue
        skills_list.append({"name": sk.name, "description": sk.description, "triggers": sk.triggers,
                            "depends_on": sk.depends_on, "roles": sk.roles, "model_tier": sk.model_tier})
    return json.dumps({"skills": skills_list})


@tool(name="skill_chain", description="Execute a list of skills sequentially",
         schema={"type": "object", "properties": {"skills": {"type": "array", "items": {"type": "string"}}, "mode": {"type": "string", "enum": ["sequential", "parallel"], "default": "sequential"}, "context": {"type": "object", "default": {}}}, "required": ["skills"]})
async def _handle_skill_chain(ctx: ServerContext, arguments: dict) -> str:
    res = await ctx.orchestrator.execute_skill_chain(ctx.skill_loader, arguments.get("skills", []),
                                                      arguments.get("mode", "sequential"), arguments.get("context", {}), router=ctx.router)
    for skill_name, skill_result in (res.get("results") or {}).items():
        await _record_skill_execution(ctx, tool="skill_chain", skill_name=skill_name, result=skill_result)
    return json.dumps(res)


@tool(name="suggest_skill", description="Recommend best skill for a given user message",
         schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
async def _handle_suggest_skill(ctx: ServerContext, arguments: dict) -> str:
    text = arguments.get("text", "")
    match = ctx.skill_loader.match_skill(text)
    if match:
        return json.dumps({"skill": match.name, "description": match.description})
    scored = sorted([{"name": sk.name, "score": sum(1 for t in sk.triggers if t.lower() in text.lower()) / max(len(sk.triggers), 1),
                      "description": sk.description} for sk in ctx.skill_loader.skills.values()], key=lambda x: x["score"], reverse=True)[:3]
    return json.dumps({"top_matches": scored, "note": "No high-confidence match"})
