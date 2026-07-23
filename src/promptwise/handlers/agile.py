"""handlers.agile -- agile method + governance MCP tool handlers (moved
verbatim from server.py's "Agile method + governance (additive)" section
during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json
from pathlib import Path

from promptwise.core.tool_registry import (
    ServerContext, tool, _record_route_verdict, _record_effort_verdict, _get_audit_log,
)


@tool(name="agile_plan", description="Two-phase, persona-aware agile plan (analyst->pm->[ux]->architect->po, then per-story sm->dev->qa loop) layered on the workflow classifier; carries the compliance gate and model-tier routing",
         schema={"type": "object", "properties": {"task": {"type": "string"}, "regulated": {"type": "boolean"}, "brownfield": {"type": "boolean"}}, "required": ["task"]})
async def _handle_agile_plan(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.agile_planner import AgilePlanner
    cfg_path = Path(__file__).resolve().parents[3] / "config" / "agile.yaml"
    plan = AgilePlanner(config_path=cfg_path).plan(
        arguments.get("task", ""), arguments.get("regulated"), arguments.get("brownfield"))
    return json.dumps(plan.to_dict())


@tool(name="shard_doc", description="Split a PRD/architecture markdown document into focused, anchored shards by heading level",
         schema={"type": "object", "properties": {"markdown": {"type": "string"}, "by_level": {"type": "integer", "default": 2}}, "required": ["markdown"]})
async def _handle_shard_doc(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.doc_sharder import DocSharder
    shards = DocSharder().shard(arguments.get("markdown", ""), int(arguments.get("by_level", 2)))
    return json.dumps([s.__dict__ for s in shards])


@tool(name="draft_story", description="Assemble a self-contained, context-engineered story: embeds architecture shards, constraints, and compliance rules inline so the dev executor needs no external lookup",
         schema={"type": "object", "properties": {"story_id": {"type": "string"}, "title": {"type": "string"}, "epic_id": {"type": "string", "default": ""}, "acceptance_criteria": {"type": "array", "items": {"type": "string"}, "default": []}, "arch_shards": {"type": "array", "items": {"type": "object"}, "default": []}, "files_to_touch": {"type": "array", "items": {"type": "string"}, "default": []}, "constraints": {"type": "array", "items": {"type": "string"}, "default": []}, "compliance_rules": {"type": "array", "items": {"type": "string"}, "default": []}, "tasks": {"type": "array", "items": {"type": "string"}, "default": []}}, "required": ["story_id", "title"]})
async def _handle_draft_story(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.story_context import StoryContextBuilder
    story = StoryContextBuilder().build(
        story_id=arguments.get("story_id", ""), title=arguments.get("title", ""),
        epic_id=arguments.get("epic_id", ""),
        acceptance_criteria=arguments.get("acceptance_criteria", []),
        arch_shards=arguments.get("arch_shards", []),
        files_to_touch=arguments.get("files_to_touch", []),
        constraints=arguments.get("constraints", []),
        compliance_rules=arguments.get("compliance_rules", []),
        tasks=arguments.get("tasks", []))
    return json.dumps({"story": story.to_dict(), "markdown": story.to_markdown()})


@tool(name="run_quality_gate", description="Issue an advisory, auditable quality-gate decision (PASS/CONCERNS/FAIL/WAIVED) from findings, risk score, and NFR assessment",
         schema={"type": "object", "properties": {"story_id": {"type": "string"}, "findings": {"type": "array", "items": {"type": "object"}, "default": []}, "risk_score": {"type": "integer", "default": 0}, "nfr_assessment": {"type": "object", "default": {}}, "waiver_reason": {"type": "string", "default": ""}, "route_id": {"type": "string", "description": "Optional: route_id from a prior route_request; folds this gate verdict back onto that route's learning outcome"}, "effort_id": {"type": "string", "description": "Optional: effort_id from a prior route_request; folds this gate verdict back onto that effort decision's learning outcome"}}, "required": ["story_id"]})
async def _handle_run_quality_gate(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.quality_gate import QualityGate
    res = QualityGate().evaluate(
        arguments.get("story_id", ""), arguments.get("findings", []),
        int(arguments.get("risk_score", 0)), arguments.get("nfr_assessment", {}),
        arguments.get("waiver_reason", ""))
    _record_route_verdict(arguments.get("route_id"), res.decision)  # WP8.1 loop close (fail-open)
    _record_effort_verdict(arguments.get("effort_id"), res.decision)  # effort-axis loop close (fail-open)
    return json.dumps(res.to_dict())


@tool(name="check_policy", description="Evaluate a proposed action (model tier, cost, operation, gates) against the cross-agent governance policy; returns allow/block with recorded reasons",
         schema={"type": "object", "properties": {"model_tier": {"type": "string"}, "estimated_cost": {"type": "number"}, "spent_so_far": {"type": "number"}, "operation": {"type": "string"}, "gates_passed": {"type": "array", "items": {"type": "string"}, "default": []}, "policy_path": {"type": "string", "default": "config/policy.yaml"}}})
async def _handle_check_policy(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.policy import Policy
    policy_path = arguments.get("policy_path", "config/policy.yaml")
    try:
        pol = Policy.from_yaml(policy_path)
    except FileNotFoundError:
        return json.dumps({"error": f"policy file not found: {policy_path} (copy config/policy.example.yaml -> config/policy.yaml)", "type": "PolicyNotConfigured"})
    dec = pol.evaluate_action(
        model_tier=arguments.get("model_tier"), estimated_cost=arguments.get("estimated_cost"),
        spent_so_far=arguments.get("spent_so_far"), operation=arguments.get("operation"),
        gates_passed=arguments.get("gates_passed", []))
    return json.dumps(dec.to_dict())


@tool(name="record_audit", description="Append a tamper-evident, hash-chained audit record of an AI-assisted change ('the trace'); returns the record and chain verification status",
         schema={"type": "object", "properties": {"task": {"type": "string"}, "agent": {"type": "string", "default": ""}, "model": {"type": "string", "default": ""}, "cost_usd": {"type": "number", "default": 0.0}, "rules_applied": {"type": "array", "items": {"type": "string"}, "default": []}, "gate_decision": {"type": "string", "default": ""}, "compliance_decision": {"type": "string", "default": ""}, "files_touched": {"type": "array", "items": {"type": "string"}, "default": []}}, "required": ["task"]})
async def _handle_record_audit(ctx: ServerContext, arguments: dict) -> str:
    audit = _get_audit_log()
    rec = audit.append(
        arguments.get("task", ""), agent=arguments.get("agent", ""), model=arguments.get("model", ""),
        cost_usd=float(arguments.get("cost_usd", 0.0)), rules_applied=arguments.get("rules_applied", []),
        gate_decision=arguments.get("gate_decision", ""), compliance_decision=arguments.get("compliance_decision", ""),
        files_touched=arguments.get("files_touched", []))
    ok, msg = audit.verify()
    return json.dumps({"record": rec.__dict__, "chain_ok": ok, "chain_msg": msg})


@tool(name="export_audit", description="Export the full AI-change audit trail (portable JSON + human-readable text) with hash-chain verification status",
         schema={"type": "object", "properties": {"format": {"type": "string", "enum": ["json", "text", "both"], "default": "both"}}})
async def _handle_export_audit(ctx: ServerContext, arguments: dict) -> str:
    audit = _get_audit_log()
    ok, msg = audit.verify()
    fmt = arguments.get("format", "both")
    out = {"chain_ok": ok, "chain_msg": msg, "record_count": len(audit.records)}
    if fmt in ("json", "both"):
        out["json"] = json.loads(audit.export_json())
    if fmt in ("text", "both"):
        out["text"] = audit.export_text()
    return json.dumps(out)


@tool(name="sync_agent_config", description="Compile one governance source (policy + packs + method) into every agent's native rules file (CLAUDE.md, AGENTS.md, .cursor/rules, copilot-instructions, .clinerules, GEMINI.md, .windsurfrules, .aiassistant/rules). Non-destructive: only the managed block is regenerated; user edits are preserved",
         schema={"type": "object", "properties": {"project": {"type": "string"}, "policy_summary": {"type": "array", "items": {"type": "string"}, "default": []}, "packs": {"type": "array", "items": {"type": "string"}, "default": []}, "rules": {"type": "array", "items": {"type": "string"}, "default": []}, "repo_root": {"type": "string", "default": "."}, "targets": {"type": "array", "items": {"type": "string"}}, "path_rules": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}, "description": "glob -> path-scoped rules (Copilot .github/instructions/*)"}, "mode": {"type": "string", "enum": ["apply", "preview", "check"], "default": "apply"}, "adopt": {"type": "boolean", "default": False}}, "required": ["project"]})
async def _handle_sync_agent_config(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.config_emitter import ConfigEmitter, GovernanceBundle
    bundle = GovernanceBundle.from_context(arguments)
    res = ConfigEmitter().sync(
        bundle, arguments.get("repo_root", "."), arguments.get("targets"),
        mode=arguments.get("mode", "apply"), adopt=arguments.get("adopt", False))
    return json.dumps({"written": res})


@tool(name="detect_agents", description="Detect which coding agents a repo is configured for (CLAUDE.md, AGENTS.md, .cursor/rules, copilot) + confidence + recommended targets",
         schema={"type": "object", "properties": {"repo_root": {"type": "string", "default": "."}}})
async def _handle_detect_agents(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.agent_detector import detect_agents
    d = detect_agents(arguments.get("repo_root", "."))
    return json.dumps({"targets": d.targets, "confidence": d.confidence, "fingerprints": d.fingerprints})


@tool(name="build_context_model", description="Derive structured intent/role/stack/domain/regulated context from a prompt (+ optional repo) to drive config emission",
         schema={"type": "object", "properties": {"text": {"type": "string"}, "repo_root": {"type": "string", "default": "."}}, "required": ["text"]})
async def _handle_build_context_model(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.context_model import build_context_model
    cm = build_context_model(arguments["text"], arguments.get("repo_root", "."))
    return json.dumps({"intent": cm.intent, "role": cm.role, "stack": cm.stack,
                       "domain": cm.domain, "regulated": cm.regulated})


@tool(name="propose_agent_config", description="Preview a unified diff of the agent rules files PromptWise would write, per target, WITHOUT writing — the review step before apply",
         schema={"type": "object", "properties": {"project": {"type": "string"}, "policy_summary": {"type": "array", "items": {"type": "string"}, "default": []}, "packs": {"type": "array", "items": {"type": "string"}, "default": []}, "rules": {"type": "array", "items": {"type": "string"}, "default": []}, "text": {"type": "string"}, "repo_root": {"type": "string", "default": "."}, "targets": {"type": "array", "items": {"type": "string"}}, "path_rules": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}}, "adopt": {"type": "boolean", "default": False}}, "required": ["project"]})
async def _handle_propose_agent_config(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.config_emitter import ConfigEmitter, GovernanceBundle
    from promptwise.core.agent_detector import detect_agents
    root = arguments.get("repo_root", ".")
    targets = arguments.get("targets") or detect_agents(root).targets
    bundle = GovernanceBundle.from_context(arguments)
    return json.dumps(ConfigEmitter().diff(bundle, root, targets, adopt=arguments.get("adopt", False)))


@tool(name="lint_agent_config", description="Lint an agent rules file (or content) for token tax, byte caps, missing .mdc frontmatter, and inferable bloat",
         schema={"type": "object", "properties": {"content": {"type": "string"}, "path": {"type": "string"}, "fmt": {"type": "string", "enum": ["md", "mdc"], "default": "md"}, "max_bytes": {"type": "integer"}, "always_apply": {"type": "boolean", "default": False}, "token_budget": {"type": "integer", "default": 0}}})
async def _handle_lint_agent_config(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.config_linter import ConfigLinter
    linter = ConfigLinter()
    kw = {"fmt": arguments.get("fmt", "md"), "max_bytes": arguments.get("max_bytes"),
          "always_apply": arguments.get("always_apply", False), "token_budget": arguments.get("token_budget", 0)}
    if arguments.get("path"):
        res = linter.lint_file(arguments["path"], **kw)
    else:
        res = linter.lint(arguments.get("content", ""), **kw)
    return json.dumps({"valid": res.valid,
                       "issues": [{"severity": i.severity, "message": i.message, "line": i.line} for i in res.issues]})


@tool(name="check_portability", description="Cross-host portability check (Phase 7 §7.4): verify the emitted governance configs for every supported host (CLAUDE.md, AGENTS.md, .cursor/rules, copilot, .clinerules, GEMINI.md, .windsurfrules, .aiassistant/rules) are present, well-formed, and in sync with the current skill/agent surface (skill_packs / agents / commands); reports drift precisely. Set emit_ci to also return a host-neutral CI-snippet that runs the governance gates using tiers/families only. Offline.",
         schema={"type": "object", "properties": {"repo_root": {"type": "string", "default": "."}, "hosts": {"type": "array", "items": {"type": "string"}, "description": "subset of supported hosts to check; default all"}, "emit_ci": {"type": "boolean", "default": False, "description": "also return a host-neutral CI-snippet"}}})
async def _handle_check_portability(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.portability_check import check_portability, emit_ci_snippet
    rep = check_portability(arguments.get("repo_root", "."), hosts=arguments.get("hosts"))
    out = rep.to_dict()
    if arguments.get("emit_ci", False):
        out["ci_snippet"] = emit_ci_snippet()
    return json.dumps(out)


@tool(name="export_web_bundle", description="Flatten one governance source (policy + packs + method) into a SINGLE self-contained, pasteable file for web-chat hosts with no IDE/CLI/MCP support (ChatGPT, Gemini, Claude.ai web chat). Not a managed-block IDE config: every call fully regenerates the bundle, there is no user-owned region to preserve. Set out_path to also write it to disk.",
         schema={"type": "object", "properties": {"project": {"type": "string"}, "policy_summary": {"type": "array", "items": {"type": "string"}, "default": []}, "packs": {"type": "array", "items": {"type": "string"}, "default": []}, "rules": {"type": "array", "items": {"type": "string"}, "default": []}, "text": {"type": "string"}, "skill_root": {"type": "string", "default": "skill_packs"}, "include_packs": {"type": "boolean", "default": True}, "out_path": {"type": "string", "description": "optional path to also write the bundle as a single file"}}, "required": ["project"]})
async def _handle_export_web_bundle(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.config_emitter import GovernanceBundle
    from promptwise.core.web_bundle import WebBundleEmitter
    bundle = GovernanceBundle.from_context(arguments)
    emitter = WebBundleEmitter()
    kw = {"skill_root": arguments.get("skill_root", "skill_packs"),
          "include_packs": arguments.get("include_packs", True)}
    out_path = arguments.get("out_path")
    if out_path:
        content = emitter.write(bundle, out_path, **kw)
        return json.dumps({"written": out_path, "bytes": len(content.encode("utf-8"))})
    content = emitter.render(bundle, **kw)
    return json.dumps({"bundle": content, "bytes": len(content.encode("utf-8"))})
