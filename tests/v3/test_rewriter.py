"""Tests for Rewriter."""

from promptwise_v3.core.rewriter import Rewriter


def test_rewrite_empty():
    r = Rewriter()
    result = r.rewrite("")
    assert result.rewritten == ""


def test_rewrite_general():
    r = Rewriter()
    result = r.rewrite("Write a function")
    assert "Write a function" in result.rewritten


def test_rewrite_with_role():
    r = Rewriter()
    result = r.rewrite("Write a function", role="developer")
    assert "senior software engineer" in result.rewritten
    assert "Write a function" in result.rewritten


def test_rewrite_filler_removal():
    r = Rewriter()
    result = r.rewrite("Basically, just write a function, you know?")
    assert result.saving_pct > 0


def test_rewrite_all_roles():
    r = Rewriter()
    for role in ("developer", "analyst", "manager", "security", "IT", "designer",
                 "writer", "researcher", "pm", "general"):
        result = r.rewrite("Solve this problem", role=role)
        assert len(result.rewritten) > 0


def test_rewrite_large_prompt_warning():
    r = Rewriter()
    result = r.rewrite("word " * 60000, role="developer")
    assert result.warning is not None
