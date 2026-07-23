"""handlers.scheduled_export -- scheduled org/compliance report export MCP
tool handler (moved verbatim from server.py's "Scheduled org/compliance
report export (Phase 16)" section during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="export_org_report", description="Build a periodic summary (spend, security-scan verdicts, governance/governor actions) for a stakeholder who doesn't touch a CLI. Markdown or self-contained HTML; no PDF dependency. Pass out_path to write it; omit to just return the report data. Offline; no network.",
         schema={"type": "object", "properties": {
             "window_days": {"type": "integer", "default": 30, "minimum": 1, "maximum": 365},
             "format": {"type": "string", "enum": ["markdown", "html"], "default": "markdown"},
             "out_path": {"type": "string", "description": "optional path to write the report"},
             "repo_root": {"type": "string", "default": "."}}})
async def _handle_export_org_report(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.report_export import export_report
    return json.dumps(export_report(
        repo_root=arguments.get("repo_root", "."),
        window_days=int(arguments.get("window_days", 30)),
        out_path=arguments.get("out_path"),
        fmt=arguments.get("format", "markdown")))
