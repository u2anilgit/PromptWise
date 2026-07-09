"""core/statusline - an at-a-glance terminal badge: "budget: 40% used | last
scan: 2h ago". Reuses the exact state the dashboard already reads
(BudgetGuardian's effective limit + the shared cost_logs DB, and
core/security_log.SecurityScanStore for the last scan) - no new state store.
Pure sync stdlib I/O (sqlite3 directly, not the async SQLAlchemy layer) so it
runs instantly from a shell prompt/statusline hook.
"""
from __future__ import annotations

import sqlite3

from promptwise.core import statusline as sl


# -- gather_status(): sync, reuses existing state ------------------------------
def test_gather_status_zero_state(tmp_path, monkeypatch):
    import promptwise.db.models as models
    monkeypatch.setattr(models, "get_db_path", lambda: tmp_path / "promptwise.db")
    status = sl.gather_status()
    assert status["budget_used_usd"] == 0.0
    assert status["budget_pct"] == 0.0
    assert status["last_scan_iso"] is None


def test_gather_status_reads_cost_logs_and_budget_overlay(tmp_path, monkeypatch):
    import promptwise.db.models as models
    db_path = tmp_path / "promptwise.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE cost_logs (log_id TEXT, session_id TEXT, ts TEXT, tool TEXT, "
        "model TEXT, input_tokens REAL, output_tokens REAL, cost_usd REAL, "
        "saving_pct REAL, lines REAL)"
    )
    conn.execute("INSERT INTO cost_logs VALUES ('1','s','t','route_request','sonnet',1,1,4.0,0,0)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(models, "get_db_path", lambda: db_path)
    (tmp_path / "budget.local.yaml").write_text("limit_usd: 10.0\n", encoding="utf-8")
    status = sl.gather_status()
    assert status["budget_used_usd"] == 4.0
    assert status["budget_limit_usd"] == 10.0
    assert status["budget_pct"] == 40.0


def test_gather_status_reads_last_scan(tmp_path, monkeypatch):
    import promptwise.db.models as models
    monkeypatch.setattr(models, "get_db_path", lambda: tmp_path / "promptwise.db")
    from promptwise.core.security_log import SecurityScanStore
    store = SecurityScanStore(db_path=tmp_path / "promptwise.db")
    store.record(checks_run=["secrets"], findings_count=0, severity_breakdown={}, passed=True,
                ts="2026-07-09T00:00:00Z")
    status = sl.gather_status()
    assert status["last_scan_iso"] == "2026-07-09T00:00:00Z"


def test_gather_status_fails_soft_when_db_unreadable(tmp_path, monkeypatch):
    import promptwise.db.models as models
    bad_path = tmp_path / "not_a_db"
    bad_path.write_text("garbage", encoding="utf-8")
    monkeypatch.setattr(models, "get_db_path", lambda: bad_path)
    status = sl.gather_status()
    assert status["budget_used_usd"] == 0.0


# -- format_statusline(): pure formatting --------------------------------------
def test_format_statusline_basic():
    text = sl.format_statusline({"budget_pct": 40.0, "budget_used_usd": 4.0, "budget_limit_usd": 10.0,
                                 "last_scan_iso": None}, now_iso="2026-07-09T12:00:00Z")
    assert text == "budget: 40% used | last scan: never"


def test_format_statusline_hours_ago():
    text = sl.format_statusline({"budget_pct": 12.3, "budget_used_usd": 1.0, "budget_limit_usd": 10.0,
                                 "last_scan_iso": "2026-07-09T10:00:00Z"}, now_iso="2026-07-09T12:00:00Z")
    assert text == "budget: 12% used | last scan: 2h ago"


def test_format_statusline_minutes_ago():
    text = sl.format_statusline({"budget_pct": 0.0, "budget_used_usd": 0.0, "budget_limit_usd": 10.0,
                                 "last_scan_iso": "2026-07-09T11:55:00Z"}, now_iso="2026-07-09T12:00:00Z")
    assert text == "budget: 0% used | last scan: 5m ago"


def test_format_statusline_just_now():
    text = sl.format_statusline({"budget_pct": 0.0, "budget_used_usd": 0.0, "budget_limit_usd": 10.0,
                                 "last_scan_iso": "2026-07-09T11:59:50Z"}, now_iso="2026-07-09T12:00:00Z")
    assert text == "budget: 0% used | last scan: just now"


def test_format_statusline_days_ago():
    text = sl.format_statusline({"budget_pct": 0.0, "budget_used_usd": 0.0, "budget_limit_usd": 10.0,
                                 "last_scan_iso": "2026-07-05T12:00:00Z"}, now_iso="2026-07-09T12:00:00Z")
    assert text == "budget: 0% used | last scan: 4d ago"


def test_format_statusline_fails_soft_on_bad_timestamp():
    text = sl.format_statusline({"budget_pct": 0.0, "budget_used_usd": 0.0, "budget_limit_usd": 10.0,
                                 "last_scan_iso": "not-a-timestamp"}, now_iso="2026-07-09T12:00:00Z")
    assert "last scan:" in text


def test_render_status_composes_gather_and_format(monkeypatch):
    monkeypatch.setattr(sl, "gather_status", lambda: {"budget_pct": 40.0, "budget_used_usd": 4.0,
                                                       "budget_limit_usd": 10.0, "last_scan_iso": None})
    text = sl.render_status()
    assert text == "budget: 40% used | last scan: never"


def test_render_status_never_raises(monkeypatch):
    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(sl, "gather_status", _boom)
    text = sl.render_status()
    assert isinstance(text, str)
    assert text  # a degraded-but-present line, not a crash
