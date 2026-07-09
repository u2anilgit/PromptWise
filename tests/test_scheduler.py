"""core/scheduler - pull-based due-check for periodic report export. No
background daemon by default: run_if_due() compares a small local marker
against a configured interval and generates a report only when due - the
same "invoked from a hook, no persistent process" pattern the rest of
PromptWise's periodic behavior already uses. A stdlib loop-based run_forever
exists for anyone who wants a real daemon cadence, started explicitly.
"""
from __future__ import annotations

import json

from promptwise.core import scheduler as sch


# -- pure due-check ------------------------------------------------------------
def test_is_due_true_when_never_run():
    assert sch.is_due(None, "2026-07-09T00:00:00Z", interval_hours=24) is True


def test_is_due_false_within_interval():
    assert sch.is_due("2026-07-09T00:00:00Z", "2026-07-09T01:00:00Z", interval_hours=24) is False


def test_is_due_true_after_interval_elapses():
    assert sch.is_due("2026-07-08T00:00:00Z", "2026-07-09T01:00:00Z", interval_hours=24) is True


def test_is_due_fails_soft_on_bad_timestamp():
    assert sch.is_due("not-a-timestamp", "2026-07-09T00:00:00Z", interval_hours=24) is True


# -- config loading --------------------------------------------------------------
def test_default_schedule_config_is_disabled():
    cfg = sch.ScheduleConfig()
    assert cfg.enabled is False
    assert cfg.interval_hours == 24


def test_load_schedule_config_missing_file_returns_disabled_default(tmp_path):
    cfg = sch.load_schedule_config(tmp_path / "does_not_exist.yaml")
    assert cfg.enabled is False


def test_load_schedule_config_reads_yaml(tmp_path):
    p = tmp_path / "reports.yaml"
    p.write_text(
        "enabled: true\ninterval_hours: 12\nformat: html\noutput_dir: .promptwise/reports\n",
        encoding="utf-8",
    )
    cfg = sch.load_schedule_config(p)
    assert cfg.enabled is True
    assert cfg.interval_hours == 12
    assert cfg.format == "html"


# -- run_if_due(): the hook-friendly entry point -------------------------------
def test_run_if_due_noop_when_disabled(tmp_path):
    cfg = sch.ScheduleConfig(enabled=False)
    result = sch.run_if_due(state_dir=tmp_path, repo_root=tmp_path, config=cfg)
    assert result["ran"] is False
    assert result["reason"] == "disabled"


def test_run_if_due_generates_report_when_due(tmp_path, monkeypatch):
    from promptwise.core import report_export as rex
    monkeypatch.setattr(rex, "gather_spend_summary", lambda **k: {"total_cost_usd": 0, "total_calls": 0, "by_model": []})
    monkeypatch.setattr(rex, "gather_security_summary", lambda **k: [])
    monkeypatch.setattr(rex, "gather_governance_summary", lambda **k: {"audit_records": 0, "chain_ok": True, "governor_actions": []})
    cfg = sch.ScheduleConfig(enabled=True, interval_hours=24, format="markdown", output_dir="reports")
    result = sch.run_if_due(state_dir=tmp_path / ".promptwise", repo_root=tmp_path, config=cfg,
                            now_iso="2026-07-09T00:00:00Z")
    assert result["ran"] is True
    assert result["path"]
    from pathlib import Path
    assert Path(result["path"]).exists()
    marker = json.loads((tmp_path / ".promptwise" / "last_report.json").read_text(encoding="utf-8"))
    assert marker["last_run"] == "2026-07-09T00:00:00Z"


def test_run_if_due_skips_when_marker_is_recent(tmp_path, monkeypatch):
    from promptwise.core import report_export as rex
    monkeypatch.setattr(rex, "gather_spend_summary", lambda **k: {})
    monkeypatch.setattr(rex, "gather_security_summary", lambda **k: [])
    monkeypatch.setattr(rex, "gather_governance_summary", lambda **k: {})
    state_dir = tmp_path / ".promptwise"
    state_dir.mkdir(parents=True)
    (state_dir / "last_report.json").write_text(json.dumps({"last_run": "2026-07-09T00:00:00Z"}), encoding="utf-8")
    cfg = sch.ScheduleConfig(enabled=True, interval_hours=24, format="markdown", output_dir="reports")
    result = sch.run_if_due(state_dir=state_dir, repo_root=tmp_path, config=cfg,
                            now_iso="2026-07-09T01:00:00Z")
    assert result["ran"] is False
    assert result["reason"] == "not_due"


def test_run_if_due_never_raises_on_generation_error(tmp_path, monkeypatch):
    from promptwise.core import report_export as rex

    def _boom(**k):
        raise RuntimeError("boom")

    monkeypatch.setattr(rex, "export_report", _boom)
    cfg = sch.ScheduleConfig(enabled=True, interval_hours=24, format="markdown", output_dir="reports")
    result = sch.run_if_due(state_dir=tmp_path / ".promptwise", repo_root=tmp_path, config=cfg,
                            now_iso="2026-07-09T00:00:00Z")
    assert result["ran"] is False
    assert "error" in result


# -- run_forever(): stdlib-loop daemon mode, opt-in, never started implicitly -
def test_run_forever_calls_run_if_due_max_iterations_times(monkeypatch):
    calls = []
    monkeypatch.setattr(sch, "run_if_due", lambda **k: calls.append(1) or {"ran": False, "reason": "disabled"})
    monkeypatch.setattr(sch.time, "sleep", lambda s: None)
    sch.run_forever(interval_seconds=0.01, max_iterations=3)
    assert len(calls) == 3
