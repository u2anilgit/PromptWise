"""Phase 11 WP11.2 — security tool handlers reuse SecurityScanner, not their
own regex copies. Response *field names* must be unchanged for callers.

Example attack/benign text is pulled from the red-team corpus by id rather
than retyped here, so this test file's own source never contains a
contiguous attack-pattern substring.
"""
import asyncio
import json

from promptwise.core.redteam_harness import builtin_cases
from promptwise.security.scanner import SecurityScanner
from promptwise import server as srv

_CASES = {c.id: c for c in builtin_cases()}


class _Ctx:
    def __init__(self):
        self.security = SecurityScanner()


def _call(name, arguments):
    return asyncio.run(srv._HANDLERS[name](_Ctx(), arguments))


def test_prompt_injection_handler_shape_unchanged():
    out = json.loads(_call("prompt_injection", {"text": _CASES["rt-injection-attack"].input_text}))
    assert set(out) == {"injection_detected", "confidence", "patterns_found", "action"}
    assert out["injection_detected"] is True


def test_owasp_scan_handler_shape_unchanged():
    out = json.loads(_call("owasp_scan", {"code": _CASES["rt-owasp-attack"].input_text}))
    assert set(out) == {"vulnerabilities", "risk_score", "passed"}
    assert out["vulnerabilities"]
    assert out["vulnerabilities"][0]["category"] == "A03:2021-SQL Injection"


def test_scan_response_handler_shape_unchanged():
    out = json.loads(_call("scan_response", {"response": _CASES["rt-pii-attack"].input_text, "original_prompt": ""}))
    assert set(out) >= {"pii_found", "pii_items", "injection_echo", "system_leak", "safe",
                       "redacted_response", "responsible_ai"}
    assert out["pii_found"] is True
    assert "example.com" not in out["redacted_response"]


def test_security_check_handler_allow_network_default_false():
    out = json.loads(_call("security_check", {"text": "hello world"}))
    assert set(out) == {"passed", "risk_score", "violations", "blocked", "details"}
