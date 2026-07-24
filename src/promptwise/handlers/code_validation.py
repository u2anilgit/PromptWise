"""handlers.code_validation -- code-validation MCP tool handler (moved
verbatim from server.py's "Code Validation" section during the handlers/
package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import (
    ServerContext, tool, _record_route_verdict, _record_effort_verdict, _record_technique_verdict,
)


@tool(name="validate_output", description="Validate generated code for syntax errors and hallucinated imports. Set use_static_analysis=true to also run a real linter (ruff for python, eslint for javascript/typescript) if installed on PATH -- opt-in, fail-open (silently skipped if the tool isn't available, never blocks the heuristic checks).",
         schema={"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string", "default": "python"}, "use_static_analysis": {"type": "boolean", "default": False}, "route_id": {"type": "string", "description": "Optional: route_id from a prior route_request; folds this verdict back onto that route's learning outcome"}, "effort_id": {"type": "string", "description": "Optional: effort_id from a prior route_request; folds this verdict back onto that effort decision's learning outcome"}, "technique_id": {"type": "string", "description": "Optional: technique_id from a prior suggest_technique; folds this verdict back onto that technique decision's learning outcome"}}, "required": ["code"]})
async def _handle_validate_output(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.code_validator.validate(arguments.get("code", ""), language=arguments.get("language", "python"),
                                     use_static_analysis=bool(arguments.get("use_static_analysis", False)))
    _record_route_verdict(arguments.get("route_id"), r.valid)  # WP8.1 loop close (fail-open)
    _record_effort_verdict(arguments.get("effort_id"), r.valid)  # effort-axis loop close (fail-open)
    _record_technique_verdict(arguments.get("technique_id"), r.valid)  # technique-axis loop close (fail-open)
    return json.dumps({"valid": r.valid, "issues": r.issues, "confidence": r.confidence, "checks_run": r.checks_run, "suggested_fix": r.suggested_fix})
