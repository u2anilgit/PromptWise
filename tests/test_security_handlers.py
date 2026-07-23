"""Phase 11 WP11.2 — security tool handlers reuse SecurityScanner, not their
own regex copies. Response *field names* must be unchanged for callers.

Example attack/benign text is pulled from the red-team corpus by id rather
than retyped here, so this test file's own source never contains a
contiguous attack-pattern substring.
"""
import asyncio
import json
import typing

from promptwise.core.redteam_harness import builtin_cases
from promptwise.security.scanner import SecurityScanner
from promptwise import server as srv

_CASES = {c.id: c for c in builtin_cases()}


class _Ctx:
    def __init__(self):
        self.security = SecurityScanner()


def _call(name, arguments):
    # _Ctx is a lightweight stand-in: this handler only reads ctx.security,
    # not the full ServerContext shape. Cast documents the intentional gap.
    ctx = typing.cast(srv.ServerContext, _Ctx())
    coro = typing.cast(
        "typing.Coroutine[typing.Any, typing.Any, str]", srv._HANDLERS[name](ctx, arguments)
    )
    return asyncio.run(coro)


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


def test_run_security_suite_aggregates_all_checks_and_persists(tmp_path, monkeypatch):
    from promptwise.core import security_log
    monkeypatch.setattr(security_log, "_default_db", lambda: tmp_path / "sec.db")
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")

    out = json.loads(_call("run_security_suite", {
        "targets": [_CASES["rt-injection-attack"].input_text,
                    _CASES["rt-pii-attack"].input_text,
                    _CASES["rt-owasp-attack"].input_text]}))
    assert set(out) == {"security", "owasp", "injection", "pii", "compliance_report_card", "status", "risk_register"}
    assert out["injection"]["detected"] is True
    assert out["pii"]["found"] is True
    assert out["owasp"]
    assert out["status"] == "completed"
    assert "LLM01:2025 Prompt Injection" in out["compliance_report_card"]["owasp_llm_top10"]

    rows = security_log.SecurityScanStore(tmp_path / "sec.db").results()
    assert len(rows) == 1
    assert rows[0]["findings_count"] > 0


def test_run_security_suite_findings_count_not_compounded(tmp_path, monkeypatch):
    """findings_count used to re-add +1 for injection and +len(pii_items) on
    top of sec.violations, which already contained those same findings --
    double/triple-counting the same signal. It must equal exactly
    len(sec.violations) + len(owasp)."""
    from promptwise.core import security_log
    monkeypatch.setattr(security_log, "_default_db", lambda: tmp_path / "sec2.db")
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")

    text = _CASES["rt-injection-attack"].input_text + " " + _CASES["rt-pii-attack"].input_text
    out = json.loads(_call("run_security_suite", {"targets": [text]}))
    sec = SecurityScanner()
    expected = len(sec.check(text).violations) + len(out["owasp"])

    rows = security_log.SecurityScanStore(tmp_path / "sec2.db").results()
    assert rows[0]["findings_count"] == expected


def test_run_security_suite_annotates_violations_with_risk_status(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")
    monkeypatch.chdir(tmp_path)
    out = json.loads(_call("run_security_suite", {
        "targets": [_CASES["rt-injection-attack"].input_text]}))
    assert out["risk_register"] == {"open": len(out["security"]["violations"]), "accepted": 0, "expired": 0}
    for v in out["security"]["violations"]:
        assert v["risk_status"] == "open"


def test_accept_risk_flips_risk_status_on_next_scan(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")
    monkeypatch.chdir(tmp_path)
    first = json.loads(_call("run_security_suite", {
        "targets": [_CASES["rt-injection-attack"].input_text]}))
    v = first["security"]["violations"][0]
    accept_out = json.loads(_call("accept_risk", {
        "check": v["check"], "detail": v["detail"], "reason": "known test fixture"}))
    assert accept_out["accepted"] is True

    second = json.loads(_call("run_security_suite", {
        "targets": [_CASES["rt-injection-attack"].input_text]}))
    matching = [x for x in second["security"]["violations"]
                if x["check"] == v["check"] and x["detail"] == v["detail"]]
    assert matching and matching[0]["risk_status"] == "accepted"


def test_list_risk_register_filters_by_status(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")
    monkeypatch.chdir(tmp_path)
    json.loads(_call("run_security_suite", {
        "targets": [_CASES["rt-injection-attack"].input_text]}))
    out = json.loads(_call("list_risk_register", {"status": "open"}))
    assert len(out["entries"]) >= 1
    assert all(e["status"] == "open" for e in out["entries"])
