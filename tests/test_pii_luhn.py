"""Phase 13.4 — Luhn checksum validation for credit-card PII.

The card regex matched any 13-16 digit run, false-positiving on order numbers
and tracking IDs. Only numbers that pass the Luhn checksum are now counted /
redacted as cards. Other PII (email, phone, SSN) is unchanged.

PII literals here are assembled from fragments so this file's own source never
contains a contiguous card number or email address.
"""
from promptwise.security.scanner import SecurityScanner, _luhn_valid

S = SecurityScanner()

_VALID_CARD = "4111" + "1111" + "1111" + "1111"        # passes Luhn (Visa test)
_VALID_SPACED = "4242 " + "4242 " + "4242 " + "4242"   # passes Luhn (spaced)
_INVALID_RUN = "1234" + "5678" + "9012" + "3456"       # fails Luhn
_EMAIL = "a.b@" + "example.com"


def test_luhn_helper():
    assert _luhn_valid(_VALID_CARD) is True
    assert _luhn_valid(_INVALID_RUN) is False


def test_valid_card_is_flagged():
    items, _ = S.detect_pii(f"my card is {_VALID_CARD}")
    assert "credit_card" in {i["type"] for i in items}


def test_valid_spaced_card_is_flagged_and_redacted():
    items, red = S.detect_pii(f"pay with {_VALID_SPACED} today", redact=True)
    assert "credit_card" in {i["type"] for i in items}
    assert _VALID_SPACED not in red


def test_invalid_run_is_not_flagged_as_card():
    items, _ = S.detect_pii(f"order number {_INVALID_RUN} shipped")
    assert "credit_card" not in {i["type"] for i in items}


def test_non_card_pii_unchanged():
    items, _ = S.detect_pii(f"reach me at {_EMAIL}")
    assert "email" in {i["type"] for i in items}
