"""CodeValidator -- heuristic checks (syntax/imports/api_patterns) plus the
opt-in real-linter layer added in
docs/superpowers/specs/2026-07-24-static-analysis-wiring-design.md.
"""
from promptwise.plugins.code_validator import CodeValidator


def test_default_behavior_unchanged_when_static_analysis_not_requested():
    validator = CodeValidator()
    result = validator.validate("import os\n")  # unused import -- a real ruff finding
    assert result.checks_run == ["syntax", "imports", "api_patterns"]
    assert "static_analysis" not in result.checks_run
    assert result.issues == []


def test_static_analysis_opt_in_surfaces_a_real_ruff_finding():
    validator = CodeValidator()
    result = validator.validate("import os\n", use_static_analysis=True)
    assert "static_analysis" in result.checks_run
    assert any(i["check"] == "static_analysis" for i in result.issues)


def test_static_analysis_opt_in_is_fail_open_when_tool_missing(monkeypatch):
    monkeypatch.setattr("promptwise.core.static_analysis.shutil.which", lambda tool: None)
    validator = CodeValidator()
    result = validator.validate("x = 1\n", use_static_analysis=True)
    assert "static_analysis" not in result.checks_run
    assert result.issues == []
    assert result.valid is True


def test_syntax_error_still_invalidates_regardless_of_static_analysis():
    validator = CodeValidator()
    result = validator.validate("def f(:\n", use_static_analysis=True)
    assert result.valid is False
    assert any(i["check"] == "syntax" for i in result.issues)
