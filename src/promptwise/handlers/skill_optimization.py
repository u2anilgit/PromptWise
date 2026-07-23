"""handlers.skill_optimization -- skill auto-optimization MCP tool handler
(moved verbatim from server.py's "Skill auto-optimization (Phase 3)"
section during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="optimize_skill_pack", description="Fold accumulated corrections (Phase 2 learning store) into a SKILL.md as a stamped, reversible managed block. Accepts the patch only if the pack's quality score strictly improves. Offline; no model required.",
         schema={"type": "object", "properties": {
             "skill_path": {"type": "string", "description": "path to the SKILL.md / pack .md to optimize"},
             "project": {"type": "string", "description": "scope corrections to a project"},
             "max_rules": {"type": "integer", "default": 8, "minimum": 1, "maximum": 25},
             "dry_run": {"type": "boolean", "default": False, "description": "score and preview without writing"}},
         "required": ["skill_path"]})
async def _handle_optimize_skill_pack(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.skill_optimizer import optimize_skill_pack
    return json.dumps(optimize_skill_pack(
        arguments.get("skill_path", ""), project=arguments.get("project"),
        max_rules=arguments.get("max_rules", 8), dry_run=arguments.get("dry_run", False)))
