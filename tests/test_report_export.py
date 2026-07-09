"""core/report_export - periodic compliance/org summary (spend, security-scan
verdicts, governance actions) for a stakeholder who does not touch a CLI.
Mirrors core/compliance_export.py's shape: pure build_report() over
already-gathered inputs, then a renderer. Markdown/HTML only - no PDF
dependency.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from promptwise.core import report_export as rex


# -- pure build_report() ------------------------------------------------------
def test_build_report_structure():
    report = rex.build_report(
        spend={"total_cost_usd": 12.5, "total_calls": 40, "by_model": []},
        security=[{"scan_id": "s1", "ts": "2026-07-01T00:00:00Z", "passed": True, "findings_count": 0}],
        governance={"audit_records": 3, "chain_ok": True, "governor_actions": []},
        window_days=30, generated_at="2026-07-09T00:00:00Z",
    )
    assert report["window_days"] == 30
    assert report["generated_at"] == "2026-07-09T00:00:00Z"
    assert report["spend"]["total_cost_usd"] == 12.5
    assert report["security"]["scan_count"] == 1
    assert report["security"]["all_passed"] is True
    assert report["governance"]["audit_records"] == 3


def test_build_report_security_all_passed_false_when_any_failed():
    report = rex.build_report(
        spend={"total_cost_usd": 0, "total_calls": 0, "by_model": []},
        security=[{"scan_id": "s1", "ts": "t", "passed": True, "findings_count": 0},
                  {"scan_id": "s2", "ts": "t", "passed": False, "findings_count": 3}],
        governance={"audit_records": 0, "chain_ok": True, "governor_actions": []},
        window_days=7,
    )
    assert report["security"]["all_passed"] is False
    assert report["security"]["scan_count"] == 2


def test_build_report_defaults_generated_at_when_omitted():
    report = rex.build_report(spend={}, security=[], governance={}, window_days=7)
    assert report["generated_at"]


# -- renderers -----------------------------------------------------------------
def test_render_markdown_includes_all_three_sections():
    report = rex.build_report(
        spend={"total_cost_usd": 5.0, "total_calls": 10, "by_model": [{"key": "sonnet", "calls": 10, "cost_usd": 5.0}]},
        security=[{"scan_id": "s1", "ts": "2026-07-01T00:00:00Z", "passed": False, "findings_count": 2}],
        governance={"audit_records": 4, "chain_ok": True, "governor_actions": [{"type": "AdjustBudgetGuard", "status": "applied"}]},
        window_days=30,
    )
    md = rex.render_markdown(report)
    assert "# PromptWise" in md
    assert "5.0" in md or "$5.00" in md
    assert "AdjustBudgetGuard" in md
    assert "chain" in md.lower()


def test_render_html_is_self_contained_and_escapes():
    report = rex.build_report(
        spend={"total_cost_usd": 1.0, "total_calls": 2, "by_model": []},
        security=[], governance={"audit_records": 0, "chain_ok": True, "governor_actions": []},
        window_days=7,
    )
    html = rex.render_html(report)
    assert "<html" in html.lower()
    assert "<script" not in html.lower()  # no external assets, no injected script


def test_write_report_markdown(tmp_path):
    report = rex.build_report(spend={}, security=[], governance={}, window_days=7)
    out = rex.write_report(report, tmp_path / "out" / "report.md", fmt="markdown")
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("# PromptWise")


def test_write_report_html(tmp_path):
    report = rex.build_report(spend={}, security=[], governance={}, window_days=7)
    out = rex.write_report(report, tmp_path / "report.html", fmt="html")
    assert out.exists()
    assert "<html" in out.read_text(encoding="utf-8").lower()


def test_write_report_rejects_unknown_format(tmp_path):
    report = rex.build_report(spend={}, security=[], governance={}, window_days=7)
    with pytest.raises(ValueError):
        rex.write_report(report, tmp_path / "report.pdf", fmt="pdf")


# -- gather_* (I/O, fail-soft) --------------------------------------------------
def test_gather_spend_summary_reads_cost_logs(tmp_path, monkeypatch):
    import promptwise.db.models as models
    db_path = tmp_path / "promptwise.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE cost_logs (log_id TEXT, session_id TEXT, ts TEXT, tool TEXT, "
        "model TEXT, input_tokens REAL, output_tokens REAL, cost_usd REAL, "
        "saving_pct REAL, lines REAL)"
    )
    conn.execute(
        "INSERT INTO cost_logs VALUES ('1','s','2026-07-01T00:00:00Z','route_request','sonnet',10,10,0.05,0,0)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(models, "get_db_path", lambda: db_path)
    summary = rex.gather_spend_summary()
    assert summary["total_calls"] == 1
    assert round(summary["total_cost_usd"], 2) == 0.05


def test_gather_spend_summary_missing_db_fails_soft(tmp_path, monkeypatch):
    import promptwise.db.models as models
    monkeypatch.setattr(models, "get_db_path", lambda: tmp_path / "does_not_exist.db")
    summary = rex.gather_spend_summary()
    assert summary["total_calls"] == 0
    assert summary["total_cost_usd"] == 0.0


def test_gather_security_summary_reads_scan_store(tmp_path):
    from promptwise.core.security_log import SecurityScanStore
    store = SecurityScanStore(db_path=tmp_path / "sec.db")
    store.record(checks_run=["secrets"], findings_count=0, severity_breakdown={}, passed=True)
    scans = rex.gather_security_summary(db_path=tmp_path / "sec.db")
    assert len(scans) == 1


def test_gather_governance_summary_reads_audit_and_proposals(tmp_path):
    from promptwise.core.audit_log import AuditLog
    audit_path = tmp_path / "audit.jsonl"
    log = AuditLog(audit_path)
    log.append(task="edit x", agent="claude-code", files_touched=["x.py"], rules_applied=["r"])
    proposals_path = tmp_path / "governor_proposals.json"
    proposals_path.write_text(json.dumps({"mode": "advise", "proposals": [{"type": "AdjustBudgetGuard", "status": "advisory"}]}), encoding="utf-8")
    gov = rex.gather_governance_summary(audit_path=audit_path, proposals_path=proposals_path)
    assert gov["audit_records"] == 1
    assert gov["chain_ok"] is True
    assert len(gov["governor_actions"]) == 1


def test_gather_governance_summary_missing_files_fails_soft(tmp_path):
    gov = rex.gather_governance_summary(audit_path=tmp_path / "nope.jsonl", proposals_path=tmp_path / "nope.json")
    assert gov["audit_records"] == 0
    assert gov["governor_actions"] == []


# -- gather_report_data() fail-soft-per-source (Phase 12 convention) ----------
def test_gather_report_data_survives_broken_source(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(rex, "gather_spend_summary", _boom)
    data = rex.gather_report_data(repo_root=".", window_days=30)
    assert data["spend"] == {}
    assert "security" in data and "governance" in data


# -- export_report(): one-shot gather + build + write --------------------------
def test_export_report_writes_a_file(tmp_path, monkeypatch):
    monkeypatch.setattr(rex, "gather_spend_summary", lambda **k: {"total_cost_usd": 1.0, "total_calls": 1, "by_model": []})
    monkeypatch.setattr(rex, "gather_security_summary", lambda **k: [])
    monkeypatch.setattr(rex, "gather_governance_summary", lambda **k: {"audit_records": 0, "chain_ok": True, "governor_actions": []})
    result = rex.export_report(out_path=tmp_path / "report.md", fmt="markdown", window_days=30)
    assert result["written"] is True
    assert (tmp_path / "report.md").exists()
