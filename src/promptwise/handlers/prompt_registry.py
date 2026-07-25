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


@tool(name="rollback_prompt", description="Roll a named prompt back to an earlier version's content by writing it as a new, current registry entry -- existing history rows are never mutated or deleted",
         schema={"type": "object", "properties": {"name": {"type": "string"}, "version": {"type": "string"}}, "required": ["name", "version"]})
async def _handle_rollback_prompt(ctx: ServerContext, arguments: dict) -> str:
    name_val = arguments.get("name", "")
    version_val = arguments.get("version", "")
    result = await ctx.memory.rollback_prompt(name_val, version_val)
    if result is None:
        return json.dumps({"error": f"Version {version_val} of '{name_val}' not found"})
    return json.dumps({"status": "rolled_back", "name": name_val, "restored_version": version_val,
                        "restored_from_prompt_id": result["source_prompt_id"], "new_prompt_id": result["new_prompt_id"]})


@tool(name="replay_prompt_version", description="Replay a registered prompt version's content through the eval harness's rubric cases to score its quality (offline record/dry-run by default), optionally diffing against another version for regression comparison",
         schema={"type": "object", "properties": {
             "name": {"type": "string"}, "version": {"type": "string"},
             "compare_version": {"type": "string", "default": ""},
             "cases": {"type": "array", "items": {"type": "object"}, "default": []},
             "cases_path": {"type": "string", "default": ""},
             "tiers": {"type": "array", "items": {"type": "string"}},
             "bar": {"type": "number", "default": 0.6}}, "required": ["name", "version"]})
async def _handle_replay_prompt_version(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.eval_harness import EvalCase, EvalHarness, EvalResultStore, load_cases
    name_val = arguments.get("name", "")
    version_val = arguments.get("version", "")
    prompt_row = await ctx.memory.get_prompt_version(name_val, version_val)
    if prompt_row is None:
        return json.dumps({"error": f"Version {version_val} of '{name_val}' not found"})

    raw_cases = list(arguments.get("cases", []))
    cases_path = arguments.get("cases_path", "")
    if cases_path:
        raw_cases.extend(c.to_dict() for c in load_cases(cases_path))
    if not raw_cases:
        raw_cases = [{"id": "default", "task_class": "prompt_replay"}]

    bar = float(arguments.get("bar", 0.6))
    tiers = arguments.get("tiers")

    def _run_version(content: str, suite: str):
        cases = [EvalCase.from_dict({**c, "prompt": content}) for c in raw_cases]
        harness = EvalHarness(runner=None, result_store=EvalResultStore(), bar=bar, suite=suite)
        return harness.run(cases, tiers=tiers)

    run = _run_version(prompt_row["content"], suite=f"prompt:{name_val}:{version_val}")
    out = {"name": name_val, "version": version_val, "run": run.to_dict()}

    compare_version = arguments.get("compare_version", "")
    if compare_version:
        cmp_row = await ctx.memory.get_prompt_version(name_val, compare_version)
        if cmp_row is None:
            out["compare_error"] = f"Version {compare_version} of '{name_val}' not found"
        else:
            cmp_run = _run_version(cmp_row["content"], suite=f"prompt:{name_val}:{compare_version}")
            out["compare_run"] = cmp_run.to_dict()
    return json.dumps(out)
