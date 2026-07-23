"""Residual-risk register -- individual findings tracked over time with
self-service accept/expire. See
docs/superpowers/specs/2026-07-24-residual-risk-register-design.md.
"""
from promptwise.security.risk_register import RiskRegister, fingerprint


def test_fingerprint_is_stable_for_same_check_and_detail():
    a = fingerprint("secrets", "hardcoded_api_key_pattern")
    b = fingerprint("secrets", "hardcoded_api_key_pattern")
    assert a == b
    assert len(a) == 16


def test_fingerprint_differs_for_different_detail():
    a = fingerprint("secrets", "pattern_one")
    b = fingerprint("secrets", "pattern_two")
    assert a != b


def test_upsert_creates_open_row(tmp_path):
    reg = RiskRegister(tmp_path / "risk.db")
    fp = reg.upsert("injection", "Injection: instruction_override", ts="2026-07-24T00:00:00Z")
    rows = reg.list()
    assert len(rows) == 1
    assert rows[0]["fingerprint"] == fp
    assert rows[0]["status"] == "open"
    assert rows[0]["first_seen"] == "2026-07-24T00:00:00Z"
    assert rows[0]["last_seen"] == "2026-07-24T00:00:00Z"


def test_upsert_twice_bumps_last_seen_not_first_seen(tmp_path):
    reg = RiskRegister(tmp_path / "risk.db")
    reg.upsert("secrets", "pattern_x", ts="2026-07-01T00:00:00Z")
    reg.upsert("secrets", "pattern_x", ts="2026-07-20T00:00:00Z")
    rows = reg.list()
    assert len(rows) == 1
    assert rows[0]["first_seen"] == "2026-07-01T00:00:00Z"
    assert rows[0]["last_seen"] == "2026-07-20T00:00:00Z"


def test_accept_sets_status_and_signoff_fields(tmp_path):
    reg = RiskRegister(tmp_path / "risk.db")
    fp = reg.upsert("permissions", "broad_grant_pattern", ts="2026-07-24T00:00:00Z")
    ok = reg.accept(fp, reason="known false positive in test fixtures",
                     expires_at="2099-01-01T00:00:00Z", accepted_by="anil")
    assert ok is True
    rows = reg.list()
    assert rows[0]["status"] == "accepted"
    assert rows[0]["accepted_reason"] == "known false positive in test fixtures"
    assert rows[0]["accepted_by"] == "anil"
    assert rows[0]["expires_at"] == "2099-01-01T00:00:00Z"


def test_accept_returns_false_for_unknown_fingerprint(tmp_path):
    reg = RiskRegister(tmp_path / "risk.db")
    assert reg.accept("0" * 16, reason="x") is False


def test_status_of_reports_expired_lazily_without_mutating_row(tmp_path):
    reg = RiskRegister(tmp_path / "risk.db")
    fp = reg.upsert("destructive", "shell_pattern", ts="2026-01-01T00:00:00Z")
    reg.accept(fp, reason="temporary", expires_at="2026-01-15T00:00:00Z")
    status = reg.status_of(fp, now_iso="2026-07-24T00:00:00Z")
    assert status == "expired"
    # the stored column is untouched -- only the computed status is "expired"
    rows = reg.list()
    assert rows[0]["status"] == "accepted"


def test_list_filters_by_computed_status(tmp_path):
    reg = RiskRegister(tmp_path / "risk.db")
    fp_open = reg.upsert("pii", "Found PII: email", ts="2026-07-24T00:00:00Z")
    fp_accepted = reg.upsert("secrets", "pattern_y", ts="2026-07-24T00:00:00Z")
    reg.accept(fp_accepted, reason="ok", expires_at="2099-01-01T00:00:00Z")
    open_rows = reg.list(status="open")
    accepted_rows = reg.list(status="accepted")
    assert [r["fingerprint"] for r in open_rows] == [fp_open]
    assert [r["fingerprint"] for r in accepted_rows] == [fp_accepted]


def test_summary_counts_by_computed_status(tmp_path):
    reg = RiskRegister(tmp_path / "risk.db")
    fp1 = reg.upsert("pii", "Found PII: email", ts="2026-07-24T00:00:00Z")
    fp2 = reg.upsert("secrets", "pattern_z", ts="2026-01-01T00:00:00Z")
    reg.accept(fp2, reason="ok", expires_at="2026-01-15T00:00:00Z")  # will be expired
    s = reg.summary(now_iso="2026-07-24T00:00:00Z")
    assert s == {"open": 1, "accepted": 0, "expired": 1}
