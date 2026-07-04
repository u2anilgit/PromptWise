"""Phase 11 WP11.2 — durable record of run_security_suite verdicts."""
from promptwise.core.security_log import SecurityScanStore


def test_record_and_read_back(tmp_path):
    store = SecurityScanStore(tmp_path / "sec.db")
    scan_id = store.record(checks_run=["secrets", "owasp"], findings_count=2,
                           severity_breakdown={"critical": 1, "high": 1, "medium": 0}, passed=False)
    assert scan_id
    rows = store.results()
    assert len(rows) == 1
    assert rows[0]["findings_count"] == 2
    assert rows[0]["passed"] is False
    assert rows[0]["severity_breakdown"] == {"critical": 1, "high": 1, "medium": 0}


def test_results_ordered_most_recent_first(tmp_path):
    store = SecurityScanStore(tmp_path / "sec.db")
    store.record(checks_run=[], findings_count=0, severity_breakdown={}, passed=True, ts="2026-01-01T00:00:00Z")
    store.record(checks_run=[], findings_count=1, severity_breakdown={}, passed=False, ts="2026-06-01T00:00:00Z")
    rows = store.results()
    assert rows[0]["ts"] == "2026-06-01T00:00:00Z"
