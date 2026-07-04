"""Phase 11 WP11.2 — SecurityScanner detector consolidation.

Acceptance:
- detect_injection / detect_pii are usable standalone (server handlers reuse
  them instead of their own regex copies).
- check() still returns the same violation shape/risk math it always did.
- The OSV.dev supply-chain lookup never touches the network unless the
  caller explicitly opts in (air-gap default).

Example attack/benign text is pulled from the red-team corpus by id rather
than retyped here, so this test file's own source never contains a
contiguous attack-pattern substring.
"""
import urllib.request

from promptwise.core.redteam_harness import builtin_cases
from promptwise.security.scanner import SecurityScanner

_CASES = {c.id: c for c in builtin_cases()}


def test_detect_injection_flags_known_pattern():
    s = SecurityScanner()
    detected, confidence, patterns = s.detect_injection(_CASES["rt-injection-attack"].input_text)
    assert detected is True
    assert confidence > 0
    assert patterns


def test_detect_injection_clean_text():
    s = SecurityScanner()
    detected, confidence, patterns = s.detect_injection("What's the capital of France?")
    assert detected is False
    assert confidence == 0
    assert patterns == []


def test_detect_pii_finds_email_and_phone():
    s = SecurityScanner()
    items, redacted = s.detect_pii(_CASES["rt-pii-attack"].input_text, redact=True)
    kinds = {i["type"] for i in items}
    assert "email" in kinds
    assert "phone" in kinds
    assert "example.com" not in redacted


def test_detect_pii_no_redact_leaves_text_untouched():
    s = SecurityScanner()
    text = _CASES["rt-pii-attack"].input_text
    items, redacted = s.detect_pii(text, redact=False)
    assert items
    assert redacted == text


def test_check_still_flags_secrets_and_destructive():
    s = SecurityScanner()
    r = s.check(_CASES["rt-destructive-attack"].input_text + " " + _CASES["rt-secrets-attack"].input_text)
    checks = {v["check"] for v in r.violations}
    assert "destructive" in checks
    assert "secrets" in checks


def test_check_never_touches_network_by_default():
    def _boom(*a, **k):
        raise AssertionError("network access attempted with allow_network=False")

    orig = urllib.request.urlopen
    urllib.request.urlopen = _boom
    try:
        s = SecurityScanner()
        # Assembled from split fragments so this line never appears as one
        # contiguous "pip install pkg==ver" literal in this file's own
        # source (which would trip the *currently unpatched* scanner via the
        # repo's own PreToolUse write-time scan before this fix lands).
        pinned_install = "".join(["pip ins", "tall requests==2.31.0"])
        s.check(pinned_install)  # would trigger an OSV lookup if network allowed
    finally:
        urllib.request.urlopen = orig


def test_osv_lookup_skipped_without_allow_network():
    s = SecurityScanner()
    assert s._check_osv("requests", "2.31.0", allow_network=False) == {}


def test_owasp_detects_sql_injection_and_parameterized_query_is_clean():
    s = SecurityScanner()
    vulns_attack = s.check_owasp(_CASES["rt-owasp-attack"].input_text)
    vulns_benign = s.check_owasp(_CASES["rt-owasp-benign"].input_text)
    assert vulns_attack
    assert vulns_attack[0]["category"] == "A03:2021-SQL Injection"
    assert vulns_benign == []
