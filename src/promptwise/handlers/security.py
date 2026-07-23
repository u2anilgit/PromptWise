"""handlers.security -- security MCP tool handlers (moved verbatim from
server.py's "Security" section during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md).

_maybe_alert_security is also used by handlers.energy_routing's
run_security_suite handler (imported from here, not duplicated)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


def _maybe_alert_security(result) -> None:
    """Best-effort, opt-in notification hook (Phase 16). Subscribes to an
    ALREADY-COMPUTED SecurityResult; never touches security/scanner.py."""
    try:
        from promptwise.core import alerts
        alerts.notify_security(result)
    except Exception:
        pass


@tool(name="security_check", description="Run security check (secrets, injection, PII, destructive, permissions). Supply-chain OSV.dev lookups are off by default (air-gap safe); set allow_network=true to opt in.",
         schema={"type": "object", "properties": {"text": {"type": "string"}, "allow_network": {"type": "boolean", "default": False}}, "required": ["text"]})
async def _handle_security_check(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.security.check(arguments.get("text", ""), allow_network=bool(arguments.get("allow_network", False)))
    _maybe_alert_security(r)
    return json.dumps({"passed": r.passed, "risk_score": r.risk_score, "violations": r.violations, "blocked": r.blocked, "details": r.details})


@tool(name="prompt_injection", description="Scan user input for prompt injection or jailbreak attempts",
         schema={"type": "object", "properties": {"text": {"type": "string"}, "threshold": {"type": "number", "default": 0.7}}, "required": ["text"]})
async def _handle_prompt_injection(ctx: ServerContext, arguments: dict) -> str:
    text = arguments.get("text", "")
    threshold = float(arguments.get("threshold", 0.7))
    detected, confidence, found = ctx.security.detect_injection(text)
    action = "block" if confidence > threshold else ("warn" if confidence > 0 else "allow")
    return json.dumps({"injection_detected": detected, "confidence": round(confidence, 2), "patterns_found": found, "action": action})


@tool(name="owasp_scan", description="Scan code for OWASP Top-10 vulnerabilities",
         schema={"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string", "default": "python"}}, "required": ["code"]})
async def _handle_owasp_scan(ctx: ServerContext, arguments: dict) -> str:
    vulns = ctx.security.check_owasp(arguments.get("code", ""))
    weights = {"critical": 3, "high": 2, "medium": 1}
    risk = sum(weights.get(v["severity"], 1) for v in vulns)
    return json.dumps({"vulnerabilities": vulns, "risk_score": risk, "passed": risk < 4})


@tool(name="scan_response", description="Scan a model response for PII leaks, injection echoes, canary leaks, and responsible-AI signals (factual grounding vs. provided sources, bias/fairness, ethical disclosure). Pass a canary token (issued via the indirect-injection canary) to flag if content that flowed through tool output/RAG leaks back into the response. Advisory.",
         schema={"type": "object", "properties": {"response": {"type": "string"}, "original_prompt": {"type": "string", "default": ""}, "sources": {"type": "string", "default": "", "description": "Source/context text the response should be grounded in; enables grounding checks"}, "canary": {"type": "string", "default": "", "description": "Canary token placed in tool-output/RAG content; flags a leak if it reappears here"}}, "required": ["response"]})
async def _handle_scan_response(ctx: ServerContext, arguments: dict) -> str:
    response = arguments.get("response", "")
    original = arguments.get("original_prompt", "")
    pii_items, redacted = ctx.security.detect_pii(response, redact=True)
    inj_detected_orig, _, _ = ctx.security.detect_injection(original)
    inj_detected_resp, _, _ = ctx.security.detect_injection(response)
    echo = inj_detected_orig and inj_detected_resp
    leak = any(p in response.lower() for p in ["system prompt", "instructions say", "i was told to"])
    # Indirect-injection canary: if a canary planted in tool-output/RAG content
    # surfaces here, that content leaked back into the response.
    canary_leak = ctx.security.check_canary_leak(response, arguments.get("canary", ""))
    # Responsible-AI advisory: grounding / bias / ethics (heuristic, never blocks).
    try:
        from promptwise.core.responsible_ai import scan as _rai_scan
        rai = _rai_scan(response, sources=arguments.get("sources", ""))
    except Exception:
        rai = {"overall": "clean", "findings": []}
    return json.dumps({"pii_found": len(pii_items) > 0, "pii_items": pii_items, "injection_echo": echo,
                       "system_leak": leak, "canary_leak": canary_leak,
                       "safe": not pii_items and not echo and not leak and not canary_leak,
                       "redacted_response": redacted, "responsible_ai": rai})


@tool(name="benchmark_injection", description="Benchmark the prompt-injection detector against a bundled offline attack+benign corpus and report measured precision/recall/F1/accuracy plus the actual false positives/negatives (a real number, not a claim). Offline by default (air-gap safe); an optional live PINT-style corpus fetch is gated behind allow_network=true.",
         schema={"type": "object", "properties": {"threshold": {"type": "number", "default": 0.0}, "corpus_path": {"type": "string", "default": ""}, "pint_url": {"type": "string", "default": ""}, "allow_network": {"type": "boolean", "default": False}}})
async def _handle_benchmark_injection(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.security.injection_benchmark import benchmark_injection_detector
    report = benchmark_injection_detector(
        ctx.security,
        threshold=float(arguments.get("threshold", 0.0)),
        corpus_path=arguments.get("corpus_path") or None,
        pint_url=arguments.get("pint_url", ""),
        allow_network=bool(arguments.get("allow_network", False)),
    )
    return json.dumps(report.to_dict())


@tool(name="accept_risk", description="Self-service accept/sign-off for a known residual risk: marks a specific finding (identified by check+detail) as accepted, with an optional expiry date. One call, no approval workflow. Does not change run_security_suite's pass/fail or risk_score -- purely a governance annotation.",
         schema={"type": "object", "properties": {"check": {"type": "string"}, "detail": {"type": "string"}, "reason": {"type": "string"}, "expires_at": {"type": "string", "default": ""}, "accepted_by": {"type": "string", "default": ""}}, "required": ["check", "detail", "reason"]})
async def _handle_accept_risk(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.security.risk_register import RiskRegister
    reg = RiskRegister()
    fp = reg.upsert(arguments.get("check", ""), arguments.get("detail", ""))
    ok = reg.accept(fp, reason=arguments.get("reason", ""),
                     expires_at=arguments.get("expires_at") or None,
                     accepted_by=arguments.get("accepted_by", ""))
    return json.dumps({"accepted": ok, "fingerprint": fp})


@tool(name="list_risk_register", description="List residual-risk register entries, optionally filtered by computed status (open/accepted/expired -- expiry is computed at read time, never mutates stored rows).",
         schema={"type": "object", "properties": {"status": {"type": "string", "enum": ["open", "accepted", "expired"], "default": ""}}})
async def _handle_list_risk_register(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.security.risk_register import RiskRegister
    reg = RiskRegister()
    status = arguments.get("status") or None
    return json.dumps({"entries": reg.list(status=status)})
