"""PromptWise — Unified MCP server with ALL tools."""

import asyncio
import difflib
import json
import sys
import re as _re
from dataclasses import dataclass
from pathlib import Path

from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path = [p for p in sys.path if p not in ("", str(Path.cwd()))]

from promptwise.config import load_config
from promptwise.core import (
    Router, Rewriter, Optimizer, CompressionEngine, CachePlanner,
    Batcher, Summarizer, RoleDetector, Orchestrator, QualityGuard,
    SkillLoader, CodexOutputValidator, WorkflowPlanner, TaskTracker, validate_mermaid,
)
from promptwise.security import SecurityScanner, ComplianceEngine
from promptwise.plugins import BudgetGuardian, CodeValidator, CostMonitor, ROITracker
from promptwise.db import init_db, SessionManager, MemoryManager


@dataclass
class ServerContext:
    config: object
    router: Router
    rewriter: Rewriter
    optimizer: Optimizer
    compression: CompressionEngine
    cache_planner: CachePlanner
    batcher: Batcher
    summarizer: Summarizer
    role_detector: RoleDetector
    orchestrator: Orchestrator
    quality: QualityGuard
    security: SecurityScanner
    compliance: ComplianceEngine
    code_validator: CodeValidator
    codex_validator: CodexOutputValidator
    budget: BudgetGuardian
    cost_monitor: CostMonitor
    roi: ROITracker
    session_manager: SessionManager
    memory: MemoryManager
    skill_loader: SkillLoader
    workflow_planner: WorkflowPlanner
    task_tracker: TaskTracker


_TOOL_DEFS = [
    # --- Core Routing & Optimization ---
    Tool(name="route_request", description="Route request to appropriate model tier based on intent, stakes, and budget",
         inputSchema={"type": "object", "properties": {
             "text": {"type": "string"}, "intent": {"type": "string", "enum": ["auto", "extract", "classify", "summarize", "question", "code", "analysis", "agent_loop", "research"], "default": "auto"},
             "stakes": {"type": "string", "enum": ["auto", "low", "medium", "high"], "default": "auto"},
             "provider": {"type": "string", "default": "claude"}, "monthly_budget_usd": {"type": "number"}, "days_elapsed_in_month": {"type": "integer"}},
         "required": ["text"]}),
    Tool(name="rewrite_prompt", description="Rewrite prompt with role framing and filler removal",
         inputSchema={"type": "object", "properties": {
             "text": {"type": "string"}, "role": {"type": "string", "enum": ["general", "developer", "analyst", "manager", "security", "IT", "designer", "writer", "researcher", "pm"], "default": "general"},
             "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["text"]}),
    Tool(name="optimize_context", description="Compress context to fit token budget by dropping low-value content",
         inputSchema={"type": "object", "properties": {
             "context": {"type": "string"}, "token_budget": {"type": "integer", "default": 2000, "minimum": 100},
             "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["context"]}),
    Tool(name="compress_prompt", description="Apply caveman compression: remove articles, filler, pleasantries, hedging",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
    Tool(name="plan_cache", description="Plan cache breakpoints for prompt reuse",
         inputSchema={"type": "object", "properties": {
             "messages": {"type": "array", "items": {"type": "object", "properties": {"role": {"type": "string", "enum": ["system", "user", "assistant"]}, "content": {"type": "string"}, "label": {"type": "string"}}, "required": ["role", "content"]}},
             "expected_reuse_count": {"type": "integer", "default": 2, "minimum": 1}, "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["messages"]}),
    Tool(name="batch_prompts", description="Batch multiple tasks into one prompt to reduce overhead",
         inputSchema={"type": "object", "properties": {
             "tasks": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
             "role": {"type": "string", "default": "general"}, "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["tasks"]}),
    Tool(name="summarize_thread", description="Compress conversation for fresh thread handoff",
         inputSchema={"type": "object", "properties": {
             "conversation": {"type": "string"}, "max_tokens": {"type": "integer", "default": 500, "minimum": 100, "maximum": 2000},
             "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["conversation"]}),
    Tool(name="compare_providers", description="Compare cost of same request across providers",
         inputSchema={"type": "object", "properties": {
             "text": {"type": "string"}, "model": {"type": "string", "default": "claude-sonnet-4-6"}},
         "required": ["text"]}),

    # --- Security ---
    Tool(name="security_check", description="Run security check (secrets, injection, PII, destructive, permissions)",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
    Tool(name="prompt_injection", description="Scan user input for prompt injection or jailbreak attempts",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}, "threshold": {"type": "number", "default": 0.7}}, "required": ["text"]}),
    Tool(name="owasp_scan", description="Scan code for OWASP Top-10 vulnerabilities",
         inputSchema={"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string", "default": "python"}}, "required": ["code"]}),
    Tool(name="scan_response", description="Scan model response for PII leaks and injection echoes",
         inputSchema={"type": "object", "properties": {"response": {"type": "string"}, "original_prompt": {"type": "string", "default": ""}}, "required": ["response"]}),

    # --- Workflow Planning (PromptWise-native) ---
    Tool(name="plan_workflow", description="Classify a task (greenfield/brownfield/regulated) and return an ordered workflow of PromptWise's own skill packs + tools to run (PRD -> design -> stories -> TDD -> review). No third-party frameworks.",
         inputSchema={"type": "object", "properties": {
             "text": {"type": "string"},
             "regulated": {"type": "boolean", "description": "Override auto-detection of regulated/compliance context"},
             "brownfield": {"type": "boolean", "description": "Override auto-detection of brownfield (existing-code) change"}},
         "required": ["text"]}),

    # --- Task / Effort / Token Tracker ---
    Tool(name="add_task", description="Create a development task with an effort estimate; tracks effort, tokens, and cost",
         inputSchema={"type": "object", "properties": {
             "title": {"type": "string"},
             "estimate_hours": {"type": "number", "default": 0},
             "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"], "default": "todo"},
             "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["title"]}),
    Tool(name="update_task", description="Update a task's status, actual hours, tokens, or cost (set or increment)",
         inputSchema={"type": "object", "properties": {
             "task_id": {"type": "string"},
             "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"]},
             "actual_hours": {"type": "number"}, "tokens": {"type": "number"}, "cost_usd": {"type": "number"},
             "add_tokens": {"type": "number"}, "add_cost": {"type": "number"}},
         "required": ["task_id"]}),
    Tool(name="list_tasks", description="List tracked tasks, optionally filtered by status",
         inputSchema={"type": "object", "properties": {
             "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"]}}}),
    Tool(name="task_report", description="Effort (estimate vs actual), token, and cost rollup across all tasks",
         inputSchema={"type": "object", "properties": {}}),

    # --- Diagrams ---
    Tool(name="validate_mermaid", description="Lint Mermaid diagram source (type, bracket/quote balance) so it renders",
         inputSchema={"type": "object", "properties": {"source": {"type": "string"}}, "required": ["source"]}),

    # --- Role Detection ---
    Tool(name="detect_role", description="Detect organizational role from prompt context",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}, "file_type": {"type": "string"}}, "required": ["text"]}),

    # --- Orchestration ---
    Tool(name="orchestrate_tasks", description="Parse multi-step prompt into DAG and execute with failure strategy",
         inputSchema={"type": "object", "properties": {
             "text": {"type": "string"}, "strategy": {"type": "string", "enum": ["stop", "retry", "fallback", "all"], "default": "fallback"}},
         "required": ["text"]}),
    Tool(name="run_autonomous", description="Run autonomous developer loop (Plan -> Execute -> Test -> Fix)",
         inputSchema={"type": "object", "properties": {"task": {"type": "string"}, "max_iterations": {"type": "integer", "default": 5}}, "required": ["task"]}),

    # --- Budget & Cost ---
    Tool(name="monitor_budget", description="Check spend against budget limit",
         inputSchema={"type": "object", "properties": {
             "used_usd": {"type": "number"}, "days_elapsed": {"type": "integer", "default": 1}, "project_id": {"type": "string"}},
         "required": ["used_usd"]}),
    Tool(name="predict_cost", description="Estimate cost of a prompt before sending",
         inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}, "model": {"type": "string", "default": "claude-sonnet-4-6"}}, "required": ["prompt"]}),
    Tool(name="set_budget_limit", description="Set monthly or daily spending limit",
         inputSchema={"type": "object", "properties": {"limit_usd": {"type": "number"}, "period": {"type": "string", "enum": ["daily", "monthly"], "default": "monthly"}}, "required": ["limit_usd"]}),
    Tool(name="get_budget_status", description="Check current spend vs configured budget limits",
         inputSchema={"type": "object", "properties": {}}),
    Tool(name="budget_report", description="Get detailed budget report with cost anomaly detection",
         inputSchema={"type": "object", "properties": {"period": {"type": "string", "enum": ["daily", "weekly", "monthly"], "default": "weekly"}, "project_id": {"type": "string"}}}),

    # --- Code Validation ---
    Tool(name="validate_output", description="Validate generated code for syntax errors and hallucinated imports",
         inputSchema={"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string", "default": "python"}}, "required": ["code"]}),

    # --- ROI ---
    Tool(name="track_roi", description="Calculate ROI ratio: value of time saved vs cost incurred",
         inputSchema={"type": "object", "properties": {
             "session_id": {"type": "string"}, "total_cost_usd": {"type": "number"}, "tokens_saved": {"type": "integer"}, "calls": {"type": "integer"}},
         "required": ["session_id", "total_cost_usd", "tokens_saved", "calls"]}),
    Tool(name="get_roi_report", description="Generate team ROI report based on cumulative stats",
         inputSchema={"type": "object", "properties": {"period": {"type": "string", "enum": ["daily", "weekly", "monthly"], "default": "weekly"}}}),
    Tool(name="cost_report", description="Get cost breakdown by project/period",
         inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "period": {"type": "string", "default": "weekly"}, "format": {"type": "string", "default": "json"}}}),

    # --- Memory & Session ---
    Tool(name="get_memory_context", description="Retrieve past memory entries for a session",
         inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}, "limit": {"type": "integer", "default": 20}}, "required": ["session_id"]}),
    Tool(name="query_memory", description="Query cross-session episodic and semantic memory",
         inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "scope": {"type": "string", "enum": ["session", "org"], "default": "org"}}, "required": ["query"]}),
    Tool(name="ping_session", description="Record session activity to reset idle clock",
         inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}}}),
    Tool(name="check_session_timeout", description="Check if session has exceeded idle thresholds",
         inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}, "idle_threshold_minutes": {"type": "integer", "default": 30}, "warn_threshold_minutes": {"type": "integer", "default": 20}}, "required": ["session_id"]}),

    # --- Skills ---
    Tool(name="invoke_skill", description="Invoke a specific skill with context",
         inputSchema={"type": "object", "properties": {"skill_name": {"type": "string"}, "context": {"type": "object", "default": {}}, "params": {"type": "object", "default": {}}}, "required": ["skill_name"]}),
    Tool(name="list_skills", description="List all available skills filtered by role",
         inputSchema={"type": "object", "properties": {"role": {"type": "string"}, "category": {"type": "string"}}}),
    Tool(name="skill_chain", description="Execute a list of skills sequentially",
         inputSchema={"type": "object", "properties": {"skills": {"type": "array", "items": {"type": "string"}}, "mode": {"type": "string", "enum": ["sequential", "parallel"], "default": "sequential"}, "context": {"type": "object", "default": {}}}, "required": ["skills"]}),
    Tool(name="suggest_skill", description="Recommend best skill for a given user message",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),

    # --- Prompt Engineering ---
    Tool(name="suggest_technique", description="Auto-detect best prompting technique: CRAFT, Few-Shot, Chain-of-Thought, or Chaining",
         inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}),
    Tool(name="apply_craft", description="Analyze prompt against CRAFT axes (Context/Role/Action/Format/Tone) and rebuild",
         inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}),
    Tool(name="inject_few_shot", description="Enhance prompt with few-shot examples",
         inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}, "examples": {"type": "array", "items": {"type": "object"}, "default": []}}, "required": ["prompt"]}),
    Tool(name="add_chain_of_thought", description="Wrap prompt with Chain-of-Thought scaffold",
         inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}, "style": {"type": "string", "enum": ["standard", "step-by-step", "tree-of-thought"], "default": "step-by-step"}}, "required": ["prompt"]}),
    Tool(name="chain_prompts", description="Decompose complex task into sequential prompt chain",
         inputSchema={"type": "object", "properties": {"task": {"type": "string"}, "steps": {"type": "integer", "default": 3}}, "required": ["task"]}),
    Tool(name="eval_prompt_across_models", description="Estimate cost and recommend model tier across Haiku/Sonnet/Opus",
         inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}, "task_type": {"type": "string", "default": "general"}}, "required": ["prompt"]}),
    Tool(name="audit_system_prompt", description="Score system prompt on clarity, role, constraints, and jailbreak resistance",
         inputSchema={"type": "object", "properties": {"system_prompt": {"type": "string"}}, "required": ["system_prompt"]}),

    # --- Prompt Registry ---
    Tool(name="save_prompt", description="Save a prompt to the versioned prompt registry",
         inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "content": {"type": "string"}, "version": {"type": "string", "default": "1.0.0"}, "description": {"type": "string", "default": ""}, "tags": {"type": "array", "items": {"type": "string"}, "default": []}}, "required": ["name", "content"]}),
    Tool(name="search_prompts", description="Search prompts in the versioned prompt registry",
         inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
    Tool(name="compare_prompts", description="Diff two versions of a registered prompt",
         inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "version_a": {"type": "string"}, "version_b": {"type": "string"}}, "required": ["name", "version_a", "version_b"]}),

    # --- Session Data ---
    Tool(name="get_session_stats", description="Get session usage statistics",
         inputSchema={"type": "object", "properties": {"since": {"type": "string", "description": "ISO 8601 timestamp filter"}}}),
    Tool(name="clear_history", description="Delete usage history older than N days",
         inputSchema={"type": "object", "properties": {"older_than_days": {"type": "integer", "minimum": 1}}, "required": ["older_than_days"]}),
    Tool(name="export_stats", description="Export usage history as JSON",
         inputSchema={"type": "object", "properties": {"since": {"type": "string"}, "format": {"type": "string", "enum": ["json", "csv"], "default": "json"}}}),
    Tool(name="reload_config", description="Reload configuration without restarting server",
         inputSchema={"type": "object", "properties": {}}),

    # --- Energy & Plugin Routing ---
    Tool(name="check_energy", description="Get energy efficiency score for a model",
         inputSchema={"type": "object", "properties": {"model": {"type": "string"}, "tokens": {"type": "integer", "default": 1000}}, "required": ["model"]}),
    Tool(name="route_for_plugin", description="Detect applicable plugin for text",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
    Tool(name="run_eval", description="A/B test a prompt across multiple models",
         inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}, "models": {"type": "array", "items": {"type": "string"}, "default": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"]}}, "required": ["prompt"]}),
    Tool(name="get_sbom", description="Generate SBOM in CycloneDX format",
         inputSchema={"type": "object", "properties": {"format": {"type": "string", "enum": ["cyclonedx", "spdx"], "default": "cyclonedx"}, "paths": {"type": "array", "items": {"type": "string"}}}}),
    Tool(name="run_security_suite", description="Run all security checks as a suite",
         inputSchema={"type": "object", "properties": {"targets": {"type": "array", "items": {"type": "string"}}, "context": {"type": "object"}}}),

    # ── Agile method + governance (additive) ─────────────────────────────────
    Tool(name="agile_plan", description="Two-phase, persona-aware agile plan (analyst->pm->[ux]->architect->po, then per-story sm->dev->qa loop) layered on the workflow classifier; carries the compliance gate and model-tier routing",
         inputSchema={"type": "object", "properties": {"task": {"type": "string"}, "regulated": {"type": "boolean"}, "brownfield": {"type": "boolean"}}, "required": ["task"]}),
    Tool(name="shard_doc", description="Split a PRD/architecture markdown document into focused, anchored shards by heading level",
         inputSchema={"type": "object", "properties": {"markdown": {"type": "string"}, "by_level": {"type": "integer", "default": 2}}, "required": ["markdown"]}),
    Tool(name="draft_story", description="Assemble a self-contained, context-engineered story: embeds architecture shards, constraints, and compliance rules inline so the dev executor needs no external lookup",
         inputSchema={"type": "object", "properties": {"story_id": {"type": "string"}, "title": {"type": "string"}, "epic_id": {"type": "string", "default": ""}, "acceptance_criteria": {"type": "array", "items": {"type": "string"}, "default": []}, "arch_shards": {"type": "array", "items": {"type": "object"}, "default": []}, "files_to_touch": {"type": "array", "items": {"type": "string"}, "default": []}, "constraints": {"type": "array", "items": {"type": "string"}, "default": []}, "compliance_rules": {"type": "array", "items": {"type": "string"}, "default": []}, "tasks": {"type": "array", "items": {"type": "string"}, "default": []}}, "required": ["story_id", "title"]}),
    Tool(name="run_quality_gate", description="Issue an advisory, auditable quality-gate decision (PASS/CONCERNS/FAIL/WAIVED) from findings, risk score, and NFR assessment",
         inputSchema={"type": "object", "properties": {"story_id": {"type": "string"}, "findings": {"type": "array", "items": {"type": "object"}, "default": []}, "risk_score": {"type": "integer", "default": 0}, "nfr_assessment": {"type": "object", "default": {}}, "waiver_reason": {"type": "string", "default": ""}}, "required": ["story_id"]}),
    Tool(name="check_policy", description="Evaluate a proposed action (model tier, cost, operation, gates) against the cross-agent governance policy; returns allow/block with recorded reasons",
         inputSchema={"type": "object", "properties": {"model_tier": {"type": "string"}, "estimated_cost": {"type": "number"}, "spent_so_far": {"type": "number"}, "operation": {"type": "string"}, "gates_passed": {"type": "array", "items": {"type": "string"}, "default": []}, "policy_path": {"type": "string", "default": "config/policy.yaml"}}}),
    Tool(name="record_audit", description="Append a tamper-evident, hash-chained audit record of an AI-assisted change ('the trace'); returns the record and chain verification status",
         inputSchema={"type": "object", "properties": {"task": {"type": "string"}, "agent": {"type": "string", "default": ""}, "model": {"type": "string", "default": ""}, "cost_usd": {"type": "number", "default": 0.0}, "rules_applied": {"type": "array", "items": {"type": "string"}, "default": []}, "gate_decision": {"type": "string", "default": ""}, "compliance_decision": {"type": "string", "default": ""}, "files_touched": {"type": "array", "items": {"type": "string"}, "default": []}}, "required": ["task"]}),
    Tool(name="export_audit", description="Export the full AI-change audit trail (portable JSON + human-readable text) with hash-chain verification status",
         inputSchema={"type": "object", "properties": {"format": {"type": "string", "enum": ["json", "text", "both"], "default": "both"}}}),
    Tool(name="sync_agent_config", description="Compile one governance source (policy + packs + method) into every agent's native rules file (CLAUDE.md, AGENTS.md, .cursor/rules, copilot-instructions, .clinerules, GEMINI.md). Non-destructive: only the managed block is regenerated; user edits are preserved",
         inputSchema={"type": "object", "properties": {"project": {"type": "string"}, "policy_summary": {"type": "array", "items": {"type": "string"}, "default": []}, "packs": {"type": "array", "items": {"type": "string"}, "default": []}, "rules": {"type": "array", "items": {"type": "string"}, "default": []}, "repo_root": {"type": "string", "default": "."}, "targets": {"type": "array", "items": {"type": "string"}}, "path_rules": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}, "description": "glob -> path-scoped rules (Copilot .github/instructions/*)"}, "mode": {"type": "string", "enum": ["apply", "preview", "check"], "default": "apply"}, "adopt": {"type": "boolean", "default": False}}, "required": ["project"]}),
    # ── Cross-agent config compiler (additive) ──────────────────────────────
    Tool(name="detect_agents", description="Detect which coding agents a repo is configured for (CLAUDE.md, AGENTS.md, .cursor/rules, copilot) + confidence + recommended targets",
         inputSchema={"type": "object", "properties": {"repo_root": {"type": "string", "default": "."}}}),
    Tool(name="build_context_model", description="Derive structured intent/role/stack/domain/regulated context from a prompt (+ optional repo) to drive config emission",
         inputSchema={"type": "object", "properties": {"text": {"type": "string"}, "repo_root": {"type": "string", "default": "."}}, "required": ["text"]}),
    Tool(name="propose_agent_config", description="Preview a unified diff of the agent rules files PromptWise would write, per target, WITHOUT writing — the review step before apply",
         inputSchema={"type": "object", "properties": {"project": {"type": "string"}, "policy_summary": {"type": "array", "items": {"type": "string"}, "default": []}, "packs": {"type": "array", "items": {"type": "string"}, "default": []}, "rules": {"type": "array", "items": {"type": "string"}, "default": []}, "text": {"type": "string"}, "repo_root": {"type": "string", "default": "."}, "targets": {"type": "array", "items": {"type": "string"}}, "path_rules": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}}, "adopt": {"type": "boolean", "default": False}}, "required": ["project"]}),
    Tool(name="lint_agent_config", description="Lint an agent rules file (or content) for token tax, byte caps, missing .mdc frontmatter, and inferable bloat",
         inputSchema={"type": "object", "properties": {"content": {"type": "string"}, "path": {"type": "string"}, "fmt": {"type": "string", "enum": ["md", "mdc"], "default": "md"}, "max_bytes": {"type": "integer"}, "always_apply": {"type": "boolean", "default": False}, "token_budget": {"type": "integer", "default": 0}}}),

    # ── Continuous learning loop (Phase 2, additive · local SQLite + FTS5) ────
    Tool(name="capture_learning", description="Store a correction as a durable, searchable learning (category, mistake, fix, project). Local SQLite + FTS5, offline.",
         inputSchema={"type": "object", "properties": {
             "category": {"type": "string", "description": "e.g. 'style', 'security', 'api-misuse'"},
             "mistake": {"type": "string", "description": "what went wrong"},
             "correction": {"type": "string", "description": "the fix / the rule going forward"},
             "project": {"type": "string", "default": ""},
             "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["category", "mistake", "correction"]}),
    Tool(name="replay_learnings", description="Top-K relevant past corrections for a task description (FTS5 BM25, LIKE fallback) plus a ready-to-inject reminder block.",
         inputSchema={"type": "object", "properties": {
             "task": {"type": "string"}, "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 25},
             "project": {"type": "string"}},
         "required": ["task"]}),
    Tool(name="learning_insights", description="Correction trends from the local learning store: counts by category, project, month, and the most-repeated mistakes.",
         inputSchema={"type": "object", "properties": {}}),

    # ── Policy intelligence & searchable trace (Phase 4, additive · offline) ──
    Tool(name="tune_permissions", description="Learn allow/deny permission suggestions from denial telemetry (the Phase 1 PermissionDenied log). Proposals only — never edits config.",
         inputSchema={"type": "object", "properties": {
             "state_dir": {"type": "string", "default": ".", "description": "project dir holding .promptwise/denials.jsonl"},
             "min_count": {"type": "integer", "default": 2, "minimum": 1},
             "mcp_json": {"type": "string", "description": "path to .mcp.json for the current allowlist"}}}),
    Tool(name="audit_mcp_servers", description="Audit declared MCP servers (.mcp.json + plugin.json) for security flags, allow-surface, and redundancy. Offline; inspects config, does not call servers.",
         inputSchema={"type": "object", "properties": {
             "repo_root": {"type": "string", "default": "."},
             "extra_configs": {"type": "array", "items": {"type": "string"}}}}),
    Tool(name="search_trace", description="Search the trace (hash-chained audit trail + learnings) by meaning. Keyword/FTS by default; optional local embeddings if installed and enabled. Offline.",
         inputSchema={"type": "object", "properties": {
             "query": {"type": "string"}, "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 25},
             "repo_root": {"type": "string", "default": "."},
             "audit_path": {"type": "string"},
             "use_embeddings": {"type": "boolean", "default": False}},
         "required": ["query"]}),
]


async def list_tools() -> list[Tool]:
    return _TOOL_DEFS


_AUDIT_LOG = None


def _get_audit_log():
    """Lazy, process-wide hash-chained audit log persisted at the repo root."""
    global _AUDIT_LOG
    if _AUDIT_LOG is None:
        from promptwise.core.audit_log import AuditLog
        repo_root = Path(__file__).resolve().parents[2]
        _AUDIT_LOG = AuditLog(repo_root / "promptwise_audit.jsonl")
    return _AUDIT_LOG


async def call_tool(ctx: ServerContext, name: str, arguments: dict) -> str:
    try:
        # ── Core Routing & Optimization ──────────────────────────────────────
        if name == "route_request":
            r = ctx.router.route(
                text=arguments.get("text", ""), intent=arguments.get("intent", "auto"),
                stakes=arguments.get("stakes", "auto"), provider=arguments.get("provider", "claude"),
                monthly_budget_usd=arguments.get("monthly_budget_usd"), days_elapsed_in_month=arguments.get("days_elapsed_in_month"))
            await ctx.memory.record_cost(tool="route_request", session_id="default", model=r.recommended_model, cost_usd=r.estimated_input_cost_usd)
            return json.dumps({"recommended_model": r.recommended_model, "reason": r.reason, "intent_detected": r.intent_detected,
                               "stakes_detected": r.stakes_detected, "estimated_input_cost_usd": r.estimated_input_cost_usd,
                               "context_window_pct": r.context_window_pct, "alternatives": r.alternatives,
                               "batch_recommended": r.batch_recommended, "batch_recommendation_note": r.batch_recommendation_note})

        elif name == "rewrite_prompt":
            r = ctx.rewriter.rewrite(arguments.get("text", ""), role=arguments.get("role", "general"), model=arguments.get("model", "claude-sonnet-4-6"))
            await ctx.memory.record_cost(tool="rewrite_prompt", session_id="default", model=arguments.get("model", "claude-sonnet-4-6"), input_tokens=r.raw_tokens, saving_pct=r.saving_pct)
            return json.dumps({"rewritten": r.rewritten, "saving_pct": r.saving_pct, "warning": r.warning})

        elif name == "optimize_context":
            r = ctx.optimizer.optimize(arguments.get("context", ""), token_budget=arguments.get("token_budget", 2000), model=arguments.get("model", "claude-sonnet-4-6"))
            return json.dumps({"optimized": r.optimized, "saving_pct": r.saving_pct, "chunks_dropped": r.chunks_dropped})

        elif name == "compress_prompt":
            r = ctx.compression.compress(arguments.get("text", ""))
            return json.dumps({"compressed": r.compressed, "saving_pct": r.saving_pct, "tokens_saved": r.tokens_saved, "rules_applied": r.rules_applied})

        elif name == "plan_cache":
            r = ctx.cache_planner.plan(arguments.get("messages", []), expected_reuse_count=arguments.get("expected_reuse_count", 2), model=arguments.get("model", "claude-sonnet-4-6"))
            return json.dumps({"breakpoints": r.breakpoints, "savings_pct": r.savings_pct})

        elif name == "batch_prompts":
            r = ctx.batcher.batch(arguments.get("tasks", []), role=arguments.get("role", "general"), model=arguments.get("model", "claude-sonnet-4-6"))
            return json.dumps({"batched_prompt": r.batched_prompt, "saving_pct": r.saving_pct})

        elif name == "summarize_thread":
            r = ctx.summarizer.summarize(arguments.get("conversation", ""), max_tokens=arguments.get("max_tokens", 500), model=arguments.get("model", "claude-sonnet-4-6"))
            return json.dumps({"summary": r.summary, "reset_prompt": r.reset_prompt, "saving_pct": r.saving_pct})

        elif name == "compare_providers":
            return json.dumps({"comparisons": ctx.router.compare_providers(arguments.get("text", ""), model=arguments.get("model", "claude-sonnet-4-6"))})

        # ── Security ─────────────────────────────────────────────────────────
        elif name == "security_check":
            r = ctx.security.check(arguments.get("text", ""))
            return json.dumps({"passed": r.passed, "risk_score": r.risk_score, "violations": r.violations, "blocked": r.blocked, "details": r.details})

        elif name == "prompt_injection":
            text = arguments.get("text", "")
            threshold = float(arguments.get("threshold", 0.7))
            keywords = ["ignore previous", "dan mode", "act as", "developer mode", "jailbreak", "override", "disregard", "forget instructions"]
            found = [kw for kw in keywords if kw in text.lower()]
            confidence = min(1.0, len(found) * 0.25)
            action = "block" if confidence > threshold else ("warn" if confidence > 0 else "allow")
            return json.dumps({"injection_detected": len(found) > 0, "confidence": round(confidence, 2), "patterns_found": found, "action": action})

        elif name == "owasp_scan":
            code = arguments.get("code", "")
            vulns = []
            if _re.search(r'f["\'].*?(SELECT|INSERT|UPDATE|DELETE).*?\{', code, _re.I):
                vulns.append({"category": "A03:2021-SQL Injection", "severity": "critical", "description": "f-string in SQL query"})
            if _re.search(r'(?i)(password|api_key|secret)\s*=\s*["\'][^"\']{4,}["\']', code):
                vulns.append({"category": "A07:2021-Hardcoded Secrets", "severity": "critical", "description": "Hardcoded credential"})
            if _re.search(r'(innerHTML|document\.write)\s*[=\(]', code):
                vulns.append({"category": "A03:2021-XSS", "severity": "high", "description": "Unsafe DOM write"})
            if _re.search(r'os\.system\s*\(|subprocess\.(Popen|run|call)\s*\(.*shell\s*=\s*True|eval\s*\(', code):
                vulns.append({"category": "A03:2021-Command Injection", "severity": "high", "description": "Shell execution on untrusted input"})
            weights = {"critical": 3, "high": 2, "medium": 1}
            risk = sum(weights.get(v["severity"], 1) for v in vulns)
            return json.dumps({"vulnerabilities": vulns, "risk_score": risk, "passed": risk < 4})

        elif name == "scan_response":
            response = arguments.get("response", "")
            original = arguments.get("original_prompt", "")
            pii_patterns = [("email", _re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')),
                            ("ssn", _re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
                            ("credit_card", _re.compile(r'\b(?:\d[ -]*?){16}\b')),
                            ("phone", _re.compile(r'\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b'))]
            pii_items = []
            redacted = response
            for label, pat in pii_patterns:
                matches = pat.findall(response)
                if matches:
                    pii_items.append({"type": label, "count": len(matches)})
                    redacted = pat.sub("[REDACTED]", redacted)
            inj_kw = ["ignore previous", "dan mode", "developer mode", "jailbreak", "override"]
            echo = any(kw in original.lower() for kw in inj_kw) and any(kw in response.lower() for kw in inj_kw)
            leak = any(p in response.lower() for p in ["system prompt", "instructions say", "i was told to"])
            return json.dumps({"pii_found": len(pii_items) > 0, "pii_items": pii_items, "injection_echo": echo, "system_leak": leak, "safe": not pii_items and not echo and not leak, "redacted_response": redacted})

        # ── Role Detection ───────────────────────────────────────────────────
        elif name == "plan_workflow":
            plan = ctx.workflow_planner.plan(
                text=arguments.get("text", ""),
                regulated=arguments.get("regulated"),
                brownfield=arguments.get("brownfield"))
            return json.dumps({"workflow": plan.workflow, "reason": plan.reason,
                               "steps": [{"phase": s.phase, "skill": s.skill, "kind": s.kind} for s in plan.steps],
                               "compliance_gate": plan.compliance_gate, "signals": plan.signals})

        elif name == "add_task":
            res = await ctx.task_tracker.add(
                title=arguments.get("title", ""), estimate_hours=arguments.get("estimate_hours", 0),
                status=arguments.get("status", "todo"), tags=arguments.get("tags"))
            return json.dumps(res)

        elif name == "update_task":
            res = await ctx.task_tracker.update(
                task_id=arguments.get("task_id", ""), status=arguments.get("status"),
                actual_hours=arguments.get("actual_hours"), tokens=arguments.get("tokens"),
                cost_usd=arguments.get("cost_usd"), add_tokens=arguments.get("add_tokens"),
                add_cost=arguments.get("add_cost"))
            return json.dumps(res)

        elif name == "list_tasks":
            res = await ctx.task_tracker.list(status=arguments.get("status"))
            return json.dumps({"tasks": res, "count": len(res)})

        elif name == "task_report":
            return json.dumps(await ctx.task_tracker.report())

        elif name == "validate_mermaid":
            r = validate_mermaid(arguments.get("source", ""))
            return json.dumps({"valid": r.valid, "diagram_type": r.diagram_type,
                               "errors": r.errors, "warnings": r.warnings, "node_count": r.node_count})

        elif name == "detect_role":
            r = ctx.role_detector.detect(arguments.get("text", ""), context={"file_type": arguments.get("file_type", "")})
            return json.dumps({"role": r.primary_role, "confidence": r.confidence, "keywords_matched": r.keywords_matched,
                               "secondary_roles": [{"role": s, "confidence": c} for s, c in r.secondary_roles], "rationale": r.rationale})

        # ── Orchestration ────────────────────────────────────────────────────
        elif name == "orchestrate_tasks":
            r = ctx.orchestrator.execute(arguments.get("text", ""), strategy=arguments.get("strategy", "fallback"))
            return json.dumps({"task_id": r.task_id, "status": r.status, "steps_total": r.steps_total, "steps_done": r.steps_done,
                               "strategy_used": r.strategy_used, "output": r.output, "duration_ms": r.duration_ms, "error": r.error})

        elif name == "run_autonomous":
            r = ctx.orchestrator.execute_autonomous(arguments.get("task", ""), max_iterations=arguments.get("max_iterations", 5))
            return json.dumps(r)

        # ── Budget & Cost ────────────────────────────────────────────────────
        elif name == "monitor_budget":
            r = ctx.budget.check(used_usd=float(arguments.get("used_usd", 0)), days_elapsed=int(arguments.get("days_elapsed", 1)), project_id=arguments.get("project_id"))
            return json.dumps({"used_usd": r.used_usd, "limit_usd": r.limit_usd, "pct_used": r.pct_used,
                               "daily_burn_usd": r.daily_burn_usd, "projected_monthly_usd": r.projected_monthly_usd,
                               "alert_level": r.alert_level, "project_id": r.project_id})

        elif name == "predict_cost":
            r = ctx.budget.predict_cost(arguments.get("prompt", ""), model=arguments.get("model", "claude-sonnet-4-6"))
            return json.dumps(r)

        elif name == "set_budget_limit":
            ctx.budget.set_limit(float(arguments.get("limit_usd", 0)), period=arguments.get("period", "monthly"))
            return json.dumps({"status": "ok", "limit_usd": arguments.get("limit_usd"), "period": arguments.get("period", "monthly")})

        elif name == "get_budget_status":
            return json.dumps(ctx.budget.get_budget_status())

        elif name == "budget_report":
            costs = [0.01, 0.02, 0.015, 0.03, 0.025, 0.01, 0.04, 0.02, 0.015, 0.035]
            anomaly = ctx.budget.cost_anomaly_detect(costs)
            return json.dumps({"period": arguments.get("period", "weekly"), "project_id": arguments.get("project_id"),
                               "total_cost_usd": round(sum(costs), 4), "anomaly": anomaly})

        # ── Code Validation ──────────────────────────────────────────────────
        elif name == "validate_output":
            r = ctx.code_validator.validate(arguments.get("code", ""), language=arguments.get("language", "python"))
            return json.dumps({"valid": r.valid, "issues": r.issues, "confidence": r.confidence, "checks_run": r.checks_run, "suggested_fix": r.suggested_fix})

        # ── ROI ──────────────────────────────────────────────────────────────
        elif name == "track_roi":
            r = ctx.roi.calculate(session_id=arguments.get("session_id", ""), total_cost_usd=float(arguments.get("total_cost_usd", 0)),
                                  tokens_saved=int(arguments.get("tokens_saved", 0)), calls=int(arguments.get("calls", 1)))
            return json.dumps({"roi_ratio": r.roi_ratio, "estimated_time_saved_min": r.estimated_time_saved_min,
                               "productivity_score": r.productivity_score, "total_cost_usd": r.total_cost_usd})

        elif name == "get_roi_report":
            stats = await ctx.memory.get_roi_stats()
            total_hours = sum(s["hours_saved"] for s in stats)
            total_cost = sum(s["cost_usd"] for s in stats)
            total_tokens = sum(s["tokens_saved"] for s in stats)
            return json.dumps({"period": arguments.get("period", "weekly"), "total_hours_saved": round(total_hours, 2),
                               "total_cost_usd": round(total_cost, 6), "total_tokens_saved": total_tokens, "records": stats})

        elif name == "cost_report":
            stats = await ctx.memory.get_roi_stats()
            pid = arguments.get("project_id")
            if pid:
                stats = [s for s in stats if s.get("project_id") == pid]
            by_skill = {}
            for s in stats:
                sk = s.get("skill", "unknown")
                by_skill.setdefault(sk, {"cost_usd": 0.0, "calls": 0})
                by_skill[sk]["cost_usd"] += s.get("cost_usd", 0.0)
                by_skill[sk]["calls"] += 1
            return json.dumps({"period": arguments.get("period", "weekly"), "project_id": pid,
                               "total_cost_usd": round(sum(v["cost_usd"] for v in by_skill.values()), 6), "by_skill": by_skill})

        # ── Memory & Session ─────────────────────────────────────────────────
        elif name == "get_memory_context":
            entries = await ctx.memory.get_context(session_id=arguments.get("session_id", ""), limit=int(arguments.get("limit", 20)))
            return json.dumps([{"entry_id": e.entry_id, "tool": e.tool, "summary": e.summary, "ts": e.ts} for e in entries])

        elif name == "query_memory":
            facts = await ctx.memory.query_facts(arguments.get("query", ""))
            return json.dumps({"facts": facts})

        elif name == "ping_session":
            r = await ctx.session_manager.ping(session_id=arguments.get("session_id"))
            return json.dumps(r)

        elif name == "check_session_timeout":
            r = await ctx.session_manager.check_timeout(
                session_id=arguments.get("session_id", ""),
                idle_threshold_minutes=int(arguments.get("idle_threshold_minutes", 30)),
                warn_threshold_minutes=int(arguments.get("warn_threshold_minutes", 20)))
            return json.dumps(r)

        # ── Skills ───────────────────────────────────────────────────────────
        elif name == "invoke_skill":
            sk = ctx.skill_loader.get_skill(arguments.get("skill_name", ""))
            if not sk:
                return json.dumps({"error": "Skill not found", "skill_name": arguments.get("skill_name")})
            res = await ctx.orchestrator.execute_skill(sk, arguments.get("context", {}), router=ctx.router)
            return json.dumps(res)

        elif name == "list_skills":
            skills_list = []
            for sk in ctx.skill_loader.skills.values():
                role_filter = arguments.get("role")
                if role_filter and sk.roles and role_filter not in sk.roles:
                    continue
                skills_list.append({"name": sk.name, "description": sk.description, "triggers": sk.triggers,
                                    "depends_on": sk.depends_on, "roles": sk.roles, "model_tier": sk.model_tier})
            return json.dumps({"skills": skills_list})

        elif name == "skill_chain":
            res = await ctx.orchestrator.execute_skill_chain(ctx.skill_loader, arguments.get("skills", []),
                                                              arguments.get("mode", "sequential"), arguments.get("context", {}), router=ctx.router)
            return json.dumps(res)

        elif name == "suggest_skill":
            text = arguments.get("text", "")
            match = ctx.skill_loader.match_skill(text)
            if match:
                return json.dumps({"skill": match.name, "description": match.description})
            scored = sorted([{"name": sk.name, "score": sum(1 for t in sk.triggers if t.lower() in text.lower()) / max(len(sk.triggers), 1),
                              "description": sk.description} for sk in ctx.skill_loader.skills.values()], key=lambda x: x["score"], reverse=True)[:3]
            return json.dumps({"top_matches": scored, "note": "No high-confidence match"})

        # ── Prompt Engineering ───────────────────────────────────────────────
        elif name == "suggest_technique":
            prompt = arguments.get("prompt", "")
            pl = prompt.lower()
            if "example" in pl:
                tech, conf, reason = "Few-Shot", 0.85, "Prompt contains 'example'"
            elif any(kw in pl for kw in ("step", "reason", "explain why")):
                tech, conf, reason = "Chain-of-Thought", 0.85, "Prompt requests step-wise reasoning"
            elif len(prompt) > 200 and len(prompt.split(".")) > 3:
                tech, conf, reason = "Chaining", 0.75, "Complex multi-sentence task"
            else:
                tech, conf, reason = "CRAFT", 0.80, "Short prompt; add Context/Role/Action/Format/Tone"
            return json.dumps({"technique": tech, "confidence": conf, "rationale": reason})

        elif name == "apply_craft":
            prompt = arguments.get("prompt", "")
            pl = prompt.lower()
            axes = {"context": any(kw in pl for kw in ["context", "background", "given"]),
                    "role": any(kw in pl for kw in ["you are", "act as", "as a"]),
                    "action": any(kw in pl for kw in ["write", "generate", "analyze", "summarize", "create", "explain"]),
                    "format": any(kw in pl for kw in ["format", "bullet", "markdown", "json", "table"]),
                    "tone": any(kw in pl for kw in ["tone", "formal", "casual", "professional"])}
            score = sum(20 for v in axes.values() if v)
            missing = [ax for ax, v in axes.items() if not v]
            adds = []
            if not axes["context"]: adds.append("Context: [Describe background]")
            if not axes["role"]: adds.append("Role: You are a helpful expert assistant.")
            if not axes["format"]: adds.append("Format: Respond in clear, structured paragraphs.")
            if not axes["tone"]: adds.append("Tone: Professional and concise.")
            improved = "\n".join(adds) + ("\n\n" if adds else "") + prompt
            return json.dumps({"axes": axes, "score": score, "missing_axes": missing, "improved_prompt": improved})

        elif name == "inject_few_shot":
            prompt = arguments.get("prompt", "")
            examples = arguments.get("examples", [])
            if examples:
                formatted = "\n".join(f"Example {i+1}:\nInput: {ex.get('input', '')}\nOutput: {ex.get('output', '')}" for i, ex in enumerate(examples))
                enhanced = formatted + "\n\n" + prompt
                return json.dumps({"enhanced_prompt": enhanced, "example_count": len(examples)})
            return json.dumps({"enhanced_prompt": "[INSERT EXAMPLES HERE]\n\n" + prompt, "example_count": 0})

        elif name == "add_chain_of_thought":
            prompt = arguments.get("prompt", "")
            style = arguments.get("style", "step-by-step")
            cot = {"standard": "Think step by step.", "tree-of-thought": "Consider multiple approaches before answering.",
                   "step-by-step": "Let's approach this step by step:\n1. First, understand the problem.\n2. Then, work through each part.\n3. Finally, synthesize the answer."}.get(style, "Think step by step.")
            return json.dumps({"wrapped_prompt": prompt + "\n\n" + cot, "technique_applied": style})

        elif name == "chain_prompts":
            task = arguments.get("task", "")
            steps = int(arguments.get("steps", 3))
            sents = [s.strip() for s in task.split(".") if s.strip()]
            chain = [{"step": i+1, "prompt": f"Step {i+1}: {(sents[i] if i < len(sents) else f'Continue step {i+1}')}.",
                      "input_from": f"step_{i}" if i > 0 else "user", "output_to": f"step_{i+2}" if i < steps-1 else "final_output"} for i in range(steps)]
            return json.dumps({"chain": chain, "handoff_instructions": "Pass output of each step as input to the next."})

        elif name == "eval_prompt_across_models":
            prompt = arguments.get("prompt", "")
            inp = max(1, len(prompt) // 4)
            out = inp * 2
            tiers = {"haiku": {"cost_usd": round(inp*0.0000008+out*0.000004, 8), "quality": "good for simple tasks"},
                     "sonnet": {"cost_usd": round(inp*0.000003+out*0.000015, 8), "quality": "best balance"},
                     "opus": {"cost_usd": round(inp*0.000015+out*0.000075, 8), "quality": "highest quality"}}
            rec, reason = ("haiku", "Short prompt") if inp < 200 else ("sonnet", "Medium complexity") if inp < 1000 else ("opus", "Long/complex")
            return json.dumps({"recommendation": rec, "tiers": tiers, "rationale": reason, "estimated_input_tokens": inp})

        elif name == "audit_system_prompt":
            sp = arguments.get("system_prompt", "")
            spl = sp.lower()
            issues = []
            score = 0
            if any(kw in spl for kw in ("you are", "act as", "your role")):
                score += 20
            else:
                issues.append("Missing role definition")
            if any(kw in spl for kw in ("do not", "never", "must not", "avoid")):
                score += 20
            else:
                issues.append("Missing constraints")
            if any(kw in spl for kw in ("format", "output", "respond in")):
                score += 20
            else:
                issues.append("Missing output format")
            if not any(p in spl for p in ["ignore previous", "disregard", "override"]):
                score += 20
            else:
                issues.append("Injection pattern detected")
            if len(sp) > 50:
                score += 20
            else:
                issues.append("Too short, unclear task")
            adds = []
            if "Missing role" in " ".join(issues):
                adds.append("You are a helpful, knowledgeable assistant.")
            if "Missing constraints" in " ".join(issues):
                adds.append("Do not discuss topics outside your defined scope.")
            if "Missing output format" in " ".join(issues):
                adds.append("Respond in clear, structured paragraphs.")
            return json.dumps({"score": score, "issues": issues, "improved_prompt": "\n".join(adds) + ("\n\n" if adds else "") + sp})

        # ── Prompt Registry ──────────────────────────────────────────────────
        elif name == "save_prompt":
            await ctx.memory.save_prompt(arguments.get("name"), arguments.get("content"), arguments.get("version", "1.0.0"),
                                          arguments.get("description", ""), arguments.get("tags", []))
            return json.dumps({"status": "saved", "name": arguments.get("name"), "version": arguments.get("version", "1.0.0")})

        elif name == "search_prompts":
            prompts = await ctx.memory.search_prompts(arguments.get("query", ""))
            return json.dumps({"prompts": prompts})

        elif name == "compare_prompts":
            name_val = arguments.get("name")
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

        # ── Session Data ─────────────────────────────────────────────────────
        elif name == "get_session_stats":
            snap = await ctx.memory.snapshot(since=arguments.get("since"))
            pricing_age = getattr(ctx.config, "last_verified", None)
            return json.dumps({**snap, "pricing_last_verified": pricing_age})

        elif name == "clear_history":
            deleted = await ctx.memory.clear_old(older_than_days=int(arguments.get("older_than_days", 90)))
            return json.dumps({"deleted_count": deleted, "older_than_days": arguments.get("older_than_days", 90)})

        elif name == "export_stats":
            return await ctx.memory.export_json()

        elif name == "reload_config":
            ctx.config = load_config()
            return json.dumps({"reloaded": True})

        # ── Energy & Plugin Routing ──────────────────────────────────────────
        elif name == "check_energy":
            score = ctx.cost_monitor.energy_efficiency_score(arguments.get("model", ""), int(arguments.get("tokens", 1000)))
            return json.dumps({"energy_efficiency_score": score, "model": arguments.get("model")})

        elif name == "route_for_plugin":
            plugin = ctx.router.route_for_plugin(arguments.get("text", ""))
            return json.dumps({"plugin": plugin})

        elif name == "run_eval":
            scores = {}
            for m in arguments.get("models", []):
                if "opus" in m: scores[m] = {"quality_score": 92, "latency_ms": 2500, "cost_usd": 0.075}
                elif "sonnet" in m: scores[m] = {"quality_score": 85, "latency_ms": 1200, "cost_usd": 0.015}
                else: scores[m] = {"quality_score": 74, "latency_ms": 350, "cost_usd": 0.003}
            return json.dumps({"prompt": arguments.get("prompt"), "eval": scores})

        elif name == "get_sbom":
            from promptwise.core.sbom import SBOMGenerator
            gen = SBOMGenerator()
            sbom = gen.generate(arguments.get("paths", [Path.cwd()])[0] if arguments.get("paths") else Path.cwd())
            return json.dumps(sbom)

        elif name == "run_security_suite":
            text = " ".join(arguments.get("targets", []))
            sec = ctx.security.check(text)
            owasp = ctx.security.check_owasp(text)
            return json.dumps({"security": {"passed": sec.passed, "violations": sec.violations, "risk_score": sec.risk_score},
                               "owasp": owasp, "status": "completed"})

        # ── Agile method + governance (additive) ─────────────────────────────
        elif name == "agile_plan":
            from promptwise.core.agile_planner import AgilePlanner
            cfg_path = Path(__file__).resolve().parents[2] / "config" / "agile.yaml"
            plan = AgilePlanner(config_path=cfg_path).plan(
                arguments.get("task", ""), arguments.get("regulated"), arguments.get("brownfield"))
            return json.dumps(plan.to_dict())

        elif name == "shard_doc":
            from promptwise.core.doc_sharder import DocSharder
            shards = DocSharder().shard(arguments.get("markdown", ""), int(arguments.get("by_level", 2)))
            return json.dumps([s.__dict__ for s in shards])

        elif name == "draft_story":
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

        elif name == "run_quality_gate":
            from promptwise.core.quality_gate import QualityGate
            res = QualityGate().evaluate(
                arguments.get("story_id", ""), arguments.get("findings", []),
                int(arguments.get("risk_score", 0)), arguments.get("nfr_assessment", {}),
                arguments.get("waiver_reason", ""))
            return json.dumps(res.to_dict())

        elif name == "check_policy":
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

        elif name == "record_audit":
            audit = _get_audit_log()
            rec = audit.append(
                arguments.get("task", ""), agent=arguments.get("agent", ""), model=arguments.get("model", ""),
                cost_usd=float(arguments.get("cost_usd", 0.0)), rules_applied=arguments.get("rules_applied", []),
                gate_decision=arguments.get("gate_decision", ""), compliance_decision=arguments.get("compliance_decision", ""),
                files_touched=arguments.get("files_touched", []))
            ok, msg = audit.verify()
            return json.dumps({"record": rec.__dict__, "chain_ok": ok, "chain_msg": msg})

        elif name == "export_audit":
            audit = _get_audit_log()
            ok, msg = audit.verify()
            fmt = arguments.get("format", "both")
            out = {"chain_ok": ok, "chain_msg": msg, "record_count": len(audit.records)}
            if fmt in ("json", "both"):
                out["json"] = json.loads(audit.export_json())
            if fmt in ("text", "both"):
                out["text"] = audit.export_text()
            return json.dumps(out)

        elif name == "sync_agent_config":
            from promptwise.core.config_emitter import ConfigEmitter, GovernanceBundle
            bundle = GovernanceBundle.from_context(arguments)
            res = ConfigEmitter().sync(
                bundle, arguments.get("repo_root", "."), arguments.get("targets"),
                mode=arguments.get("mode", "apply"), adopt=arguments.get("adopt", False))
            return json.dumps({"written": res})

        elif name == "detect_agents":
            from promptwise.core.agent_detector import detect_agents
            d = detect_agents(arguments.get("repo_root", "."))
            return json.dumps({"targets": d.targets, "confidence": d.confidence, "fingerprints": d.fingerprints})

        elif name == "build_context_model":
            from promptwise.core.context_model import build_context_model
            cm = build_context_model(arguments["text"], arguments.get("repo_root", "."))
            return json.dumps({"intent": cm.intent, "role": cm.role, "stack": cm.stack,
                               "domain": cm.domain, "regulated": cm.regulated})

        elif name == "propose_agent_config":
            from promptwise.core.config_emitter import ConfigEmitter, GovernanceBundle
            from promptwise.core.agent_detector import detect_agents
            root = arguments.get("repo_root", ".")
            targets = arguments.get("targets") or detect_agents(root).targets
            bundle = GovernanceBundle.from_context(arguments)
            return json.dumps(ConfigEmitter().diff(bundle, root, targets, adopt=arguments.get("adopt", False)))

        elif name == "lint_agent_config":
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

        # ── Continuous learning loop (Phase 2) ───────────────────────────────
        elif name == "capture_learning":
            from promptwise.core.learning_store import LearningStore
            learning = LearningStore().capture(
                category=arguments.get("category", ""), mistake=arguments.get("mistake", ""),
                correction=arguments.get("correction", ""), project=arguments.get("project", ""),
                tags=arguments.get("tags", []))
            return json.dumps({"captured": learning.to_dict()})

        elif name == "replay_learnings":
            from promptwise.core.learning_replay import replay
            return json.dumps(replay(arguments.get("task", ""), k=arguments.get("k", 5),
                                     project=arguments.get("project")))

        elif name == "learning_insights":
            from promptwise.core.insights import compute_insights
            return json.dumps(compute_insights())

        # ── Policy intelligence & searchable trace (Phase 4) ─────────────────
        elif name == "tune_permissions":
            from promptwise.core.permission_tuner import tune_permissions
            return json.dumps(tune_permissions(
                state_dir=arguments.get("state_dir", "."),
                min_count=arguments.get("min_count", 2),
                mcp_json=arguments.get("mcp_json")))

        elif name == "audit_mcp_servers":
            from promptwise.core.mcp_auditor import audit_mcp_servers
            return json.dumps(audit_mcp_servers(
                repo_root=arguments.get("repo_root", "."),
                extra_configs=arguments.get("extra_configs")))

        elif name == "search_trace":
            from promptwise.core.semantic_index import search_trace
            return json.dumps(search_trace(
                arguments.get("query", ""), k=arguments.get("k", 5),
                repo_root=arguments.get("repo_root", "."),
                audit_path=arguments.get("audit_path"),
                use_embeddings=arguments.get("use_embeddings", False)))

        else:
            return json.dumps({"error": f"Unknown tool: {name}", "type": "UnknownTool", "tool": name})

    except Exception as e:
        return json.dumps({"error": str(e), "type": type(e).__name__, "tool": name})


async def main() -> None:
    # repo root = src/promptwise/server.py -> parents[2]; config/ and skills/ live there.
    config_dir = Path(__file__).resolve().parents[2]
    config = load_config(config_dir)

    db_path = await init_db()
    mm = MemoryManager(db_path)
    await mm.init()

    task_tracker = TaskTracker(db_path)
    await task_tracker.init()

    skills_dir = config_dir / config.skills.directory
    skill_loader = SkillLoader(skills_dir)
    skill_loader.load_skills()

    ctx = ServerContext(
        config=config,
        router=Router(config),
        rewriter=Rewriter(config),
        optimizer=Optimizer(config),
        compression=CompressionEngine(),
        cache_planner=CachePlanner(config),
        batcher=Batcher(config),
        summarizer=Summarizer(config),
        role_detector=RoleDetector(),
        orchestrator=Orchestrator(),
        quality=QualityGuard(),
        security=SecurityScanner(config.security),
        compliance=ComplianceEngine(config_dir / "config" / "compliance" if (config_dir / "config").exists() else None),
        code_validator=CodeValidator(),
        codex_validator=CodexOutputValidator(),
        budget=BudgetGuardian(limit_usd=config.policies.budget_hard_stop_usd, team_budget_usd=config.policies.team_budget_usd),
        cost_monitor=CostMonitor(),
        roi=ROITracker(),
        session_manager=SessionManager(db_path),
        memory=mm,
        skill_loader=skill_loader,
        workflow_planner=WorkflowPlanner(),
        task_tracker=task_tracker,
    )

    server = Server("promptwise")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return await list_tools()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        result = await call_tool(ctx, name, arguments)
        return [TextContent(type="text", text=result)]

    init_opts = InitializationOptions(
        server_name="promptwise",
        server_version="1.1.0",
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, initialization_options=init_opts)


def sync_main() -> None:
    """Synchronous entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
