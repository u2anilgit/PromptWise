"""core.tool_registry -- the tool-registration seam and cross-category
shared helpers, extracted from server.py so handlers/*.py modules can
import ServerContext/tool without importing server.py itself (which would
create a circular import once handlers/ imports the other way).

Pure extraction: no behavior change from server.py's prior inline
definitions. See docs/superpowers/specs/2026-07-22-handlers-package-split-design.md.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from mcp.types import Tool

from promptwise.core import (
    Router, Rewriter, Optimizer, CompressionEngine, CachePlanner,
    Batcher, Summarizer, RoleDetector, Orchestrator, QualityGuard,
    SkillLoader, WorkflowPlanner, TaskTracker,
)
from promptwise.security import SecurityScanner, ComplianceEngine
from promptwise.plugins import BudgetGuardian, CodeValidator, CostMonitor, ROITracker
from promptwise.db import SessionManager, MemoryManager


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
    budget: BudgetGuardian
    cost_monitor: CostMonitor
    roi: ROITracker
    session_manager: SessionManager
    memory: MemoryManager
    skill_loader: SkillLoader
    workflow_planner: WorkflowPlanner
    task_tracker: TaskTracker


@dataclass
class _RegistryEntry:
    tool: Tool
    handler: Callable[[ServerContext, dict], Awaitable[str]]


class ToolRegistry:
    """Collects @tool-decorated handlers into one name -> (Tool, handler) map.

    One source of truth per tool, physically adjacent to its handler. Guards
    duplicate names, non-coroutine handlers, and malformed schemas at
    decoration time (import time for the real module registry) instead of
    only at test time.
    """

    def __init__(self) -> None:
        self.entries: dict[str, _RegistryEntry] = {}

    def tool(self, name: str, description: str, schema: dict):
        def _register(fn):
            if name in self.entries:
                raise ValueError(f"duplicate tool registration: {name!r}")
            if not inspect.iscoroutinefunction(fn):
                raise TypeError(f"tool handler must be a coroutine function: {name!r}")
            if not isinstance(schema, dict) or schema.get("type") != "object":
                raise TypeError(f"tool schema must be an object-type inputSchema: {name!r}")
            self.entries[name] = _RegistryEntry(
                tool=Tool(name=name, description=description, inputSchema=schema),
                handler=fn,
            )
            return fn
        return _register


_registry = ToolRegistry()
tool = _registry.tool


def _record_route_verdict(route_id, signal) -> None:
    """Correlate a later quality verdict onto a prior live route (WP8.1).

    The seam for closing the learning loop: any tool that produces a verdict for a
    route it was passed (``validate_output`` validity, ``run_quality_gate``
    decision) calls this with the ``route_id`` returned by ``route_request``.
    Fully fail-open -- never raises, never affects the tool's own result."""
    if not route_id:
        return
    try:
        from promptwise.core.route_recorder import record_route_verdict
        record_route_verdict(route_id, signal)
    except Exception:
        pass


def _record_effort_verdict(effort_id, signal) -> None:
    """Correlate a later quality verdict onto a prior live effort decision.

    Mirrors ``_record_route_verdict`` exactly, over the effort axis: any tool
    that produces a verdict for an effort decision it was passed
    (``validate_output`` validity, ``run_quality_gate`` decision) calls this
    with the ``effort_id`` returned by ``route_request``. Fully fail-open --
    never raises, never affects the tool's own result."""
    if not effort_id:
        return
    try:
        from promptwise.core.effort_recorder import record_effort_verdict
        record_effort_verdict(effort_id, signal)
    except Exception:
        pass


def _resolve_effort(intent: str, stakes: str) -> str:
    """Reasoning-effort level for a route decision: static heuristic, blended
    with the learned outcome history when PROMPTWISE_ADAPTIVE_EFFORT is on
    (default). Fail-open to the static pick on any error -- mirrors
    Router._maybe_adapt's fail-open contract exactly."""
    import os
    from promptwise.core.effort_router import static_effort
    base = static_effort(intent, stakes)
    if os.environ.get("PROMPTWISE_ADAPTIVE_EFFORT", "on").strip().lower() in ("0", "off", "false", "no"):
        return base
    try:
        from promptwise.core.effort_adapter import EffortAdapter
        adapter = EffortAdapter()
        effort, _ = adapter.adapt(f"{intent}/{stakes}", base)
        return effort
    except Exception:
        return base


async def _record_skill_execution(ctx: ServerContext, *, tool: str, skill_name: str, result: dict) -> None:
    """Log cost + audit for one skill execution. invoke_skill/skill_chain
    already return real per-call cost/model data (execute_skill's response)
    without ever persisting it -- neither cost_logs nor the audit trail saw
    it. Mirrors the fields route_request already logs. Fail-open: never
    raises, never affects the tool's own return value."""
    if result.get("status") != "success":
        return
    try:
        await ctx.memory.record_cost(
            tool=tool, session_id="default", model=result.get("model_used", ""),
            input_tokens=result.get("input_tokens", 0), output_tokens=result.get("output_tokens", 0),
            cost_usd=result.get("cost_usd", 0.0))
    except Exception:
        pass
    try:
        _get_audit_log().append(
            f"{tool}:{skill_name}", agent=skill_name, model=result.get("model_used", ""),
            cost_usd=float(result.get("cost_usd", 0.0) or 0.0))
    except Exception:
        pass


_AUDIT_LOG = None


def _get_audit_log():
    """Lazy, process-wide hash-chained audit log persisted at the repo root."""
    global _AUDIT_LOG
    if _AUDIT_LOG is None:
        from promptwise.core.audit_log import AuditLog
        repo_root = Path(__file__).resolve().parents[3]
        _AUDIT_LOG = AuditLog(repo_root / "promptwise_audit.jsonl")
    return _AUDIT_LOG
