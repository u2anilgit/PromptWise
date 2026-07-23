"""handlers.energy_routing -- energy scoring, plugin routing, and
eval/security-harness MCP tool handlers (moved verbatim from server.py's
"Energy & Plugin Routing" section during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json
from pathlib import Path

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="check_energy", description="Get energy efficiency score for a model",
         schema={"type": "object", "properties": {"model": {"type": "string"}, "tokens": {"type": "integer", "default": 1000}}, "required": ["model"]})
async def _handle_check_energy(ctx: ServerContext, arguments: dict) -> str:
    score = ctx.cost_monitor.energy_efficiency_score(arguments.get("model", ""), int(arguments.get("tokens", 1000)))
    return json.dumps({"energy_efficiency_score": score, "model": arguments.get("model")})


@tool(name="route_for_plugin", description="Detect applicable plugin for text",
         schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
async def _handle_route_for_plugin(ctx: ServerContext, arguments: dict) -> str:
    plugin = ctx.router.route_for_plugin(arguments.get("text", ""))
    return json.dumps({"plugin": plugin})


@tool(name="run_eval", description="Estimate and compare per-model cost for a prompt across multiple models (cost only -- for a real quality comparison, use run_eval_harness)",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "models": {"type": "array", "items": {"type": "string"}, "default": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"]}}, "required": ["prompt"]})
async def _handle_run_eval(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    default_models = ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"]
    scores = {m: ctx.budget.predict_cost(prompt, model=m) for m in arguments.get("models", default_models)}
    return json.dumps({"prompt": prompt, "eval": scores})


@tool(name="run_eval_harness", description="Run a durable eval + regression suite (prompt+rubric cases) offline; score with the quality gate, diff against a stored baseline to flag regressions, expose a pass/fail gate, and feed outcomes back into adaptive routing. Offline default is a record/dry-run mode (no cloud). Set save_baseline=true to bless this run as the new baseline.",
         schema={"type": "object", "properties": {"cases": {"type": "array", "items": {"type": "object"}, "default": []}, "cases_path": {"type": "string", "default": ""}, "suite": {"type": "string", "default": "default"}, "tiers": {"type": "array", "items": {"type": "string"}}, "bar": {"type": "number", "default": 0.6}, "save_baseline": {"type": "boolean", "default": False}}})
async def _handle_run_eval_harness(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.adaptive_router import OutcomeStore
    from promptwise.core.eval_harness import (
        EvalCase, EvalHarness, EvalResultStore, load_cases)
    cases = [EvalCase.from_dict(c) for c in arguments.get("cases", []) if isinstance(c, dict)]
    cases_path = arguments.get("cases_path", "")
    if cases_path:
        cases.extend(load_cases(cases_path))
    suite = arguments.get("suite", "default")
    harness = EvalHarness(
        runner=None,  # offline default: record/dry-run, never cloud
        outcome_store=OutcomeStore(), result_store=EvalResultStore(),
        bar=float(arguments.get("bar", 0.6)), suite=suite)
    run = harness.run(cases, tiers=arguments.get("tiers"))
    out = run.to_dict()
    if arguments.get("save_baseline"):
        out["baseline_saved"] = harness.save_baseline(run)
    return json.dumps(out)


@tool(name="get_sbom", description="Generate SBOM in CycloneDX format",
         schema={"type": "object", "properties": {"format": {"type": "string", "enum": ["cyclonedx", "spdx"], "default": "cyclonedx"}, "paths": {"type": "array", "items": {"type": "string"}}}})
async def _handle_get_sbom(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.sbom import SBOMGenerator
    gen = SBOMGenerator()
    sbom = gen.generate(arguments.get("paths", [Path.cwd()])[0] if arguments.get("paths") else Path.cwd())
    return json.dumps(sbom)


@tool(name="run_security_suite", description="Run all security checks as a suite",
         schema={"type": "object", "properties": {"targets": {"type": "array", "items": {"type": "string"}}, "context": {"type": "object"}}})
async def _handle_run_security_suite(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.security_log import SecurityScanStore
    from promptwise.handlers.security import _maybe_alert_security
    from promptwise.security.framework_map import build_report_card
    text = " ".join(arguments.get("targets", []))
    sec = ctx.security.check(text)
    owasp = ctx.security.check_owasp(text)
    inj_detected, inj_confidence, inj_patterns = ctx.security.detect_injection(text)
    pii_items, _ = ctx.security.detect_pii(text)
    # sec.violations (from check()) already carries the injection and PII
    # findings reported below -- don't count them a second time here.
    findings_count = len(sec.violations) + len(owasp)
    severity_breakdown = {
        "critical": sum(1 for v in owasp if v["severity"] == "critical"),
        "high": sum(1 for v in owasp if v["severity"] == "high"),
        "medium": sum(1 for v in owasp if v["severity"] == "medium"),
    }
    try:
        SecurityScanStore().record(
            checks_run=list(sec.checks_run), findings_count=findings_count,
            severity_breakdown=severity_breakdown, passed=sec.passed and not owasp)
    except Exception:
        pass  # storage is best-effort; a full disk must not sink the suite
    _maybe_alert_security(sec)
    return json.dumps({"security": {"passed": sec.passed, "violations": sec.violations, "risk_score": sec.risk_score},
                       "owasp": owasp,
                       "injection": {"detected": inj_detected, "confidence": round(inj_confidence, 2), "patterns_found": inj_patterns},
                       "pii": {"found": len(pii_items) > 0, "items": pii_items},
                       "compliance_report_card": build_report_card(sec.violations),
                       "status": "completed"})


@tool(name="run_red_team_harness", description="Run a durable, offline red-team suite against the security scanners: known attack patterns (must be caught) and benign counterexamples (must NOT be flagged) across injection/owasp/secrets/destructive/permissions/pii/supply_chain checks. Diffs against a stored baseline to flag regressions (an attack that used to be caught now escapes, or a benign input starts false-positiving) and exposes a pass/fail gate. Defaults to a built-in corpus when no cases/cases_path given. Set save_baseline=true to bless this run as the new baseline.",
         schema={"type": "object", "properties": {"cases": {"type": "array", "items": {"type": "object"}, "default": []}, "cases_path": {"type": "string", "default": ""}, "suite": {"type": "string", "default": "default"}, "save_baseline": {"type": "boolean", "default": False}}})
async def _handle_run_red_team_harness(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.redteam_harness import (
        RedTeamCase, RedTeamHarness, RedTeamResultStore, builtin_cases, load_cases)
    cases = [RedTeamCase.from_dict(c) for c in arguments.get("cases", []) if isinstance(c, dict)]
    cases_path = arguments.get("cases_path", "")
    if cases_path:
        cases.extend(load_cases(cases_path))
    if not cases and not cases_path:
        cases = builtin_cases()
    suite = arguments.get("suite", "default")
    harness = RedTeamHarness(result_store=RedTeamResultStore(), suite=suite)
    run = harness.run(cases)
    out = run.to_dict()
    if arguments.get("save_baseline"):
        out["baseline_saved"] = harness.save_baseline(run)
    return json.dumps(out)
