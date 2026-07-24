"""Real static-analysis subprocess wiring -- see
docs/superpowers/specs/2026-07-24-static-analysis-wiring-design.md.
"""
import subprocess

from promptwise.core.static_analysis import run_static_analysis


def test_clean_python_code_reports_no_issues():
    result = run_static_analysis("x = 1\n", language="python")
    assert result.tool_available is True
    assert result.tool == "ruff"
    assert result.issues == []


def test_python_code_with_real_ruff_violation_is_reported():
    # F401: unused import -- a real ruff finding, not a heuristic guess.
    result = run_static_analysis("import os\n", language="python")
    assert result.tool_available is True
    assert len(result.issues) >= 1
    assert result.issues[0]["tool"] == "ruff"
    assert result.issues[0]["check"] == "static_analysis"
    assert result.issues[0]["line"] == 1


def test_unsupported_language_is_fail_open():
    result = run_static_analysis("SELECT 1", language="sql")
    assert result.tool_available is False
    assert result.issues == []


def test_missing_binary_is_fail_open(monkeypatch):
    monkeypatch.setattr("promptwise.core.static_analysis.shutil.which", lambda tool: None)
    result = run_static_analysis("x = 1\n", language="python")
    assert result.tool_available is False
    assert result.tool == "ruff"
    assert result.issues == []


def test_timeout_is_fail_open(monkeypatch):
    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ruff", timeout=10.0)
    monkeypatch.setattr("promptwise.core.static_analysis.subprocess.run", _raise_timeout)
    result = run_static_analysis("x = 1\n", language="python")
    assert result.tool_available is False
    assert result.issues == []


def test_javascript_without_eslint_installed_is_fail_open():
    # This CI/dev box has no eslint on PATH (confirmed during design) --
    # exercises the real fail-open path, not a mock.
    result = run_static_analysis("var x = 1;\n", language="javascript")
    assert result.tool_available is False
    assert result.tool == "eslint"
