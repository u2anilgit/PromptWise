"""Tests for CodexOutputValidator."""

from promptwise_v3.core.codex_validator import CodexOutputValidator


def test_validate_code_block():
    v = CodexOutputValidator()
    result = v.validate("```python\nprint('hello')\n```")
    assert len(result.code_blocks) == 1
    assert result.valid is True


def test_validate_balanced_brackets():
    v = CodexOutputValidator()
    r1 = v.validate("```python\ndef f():\n  pass\n```")
    assert r1.valid is True
    r2 = v.validate("```python\ndef f(:\n  pass\n```")
    assert r2.is_complete is False
    assert len(r2.issues) > 0


def test_validate_empty():
    v = CodexOutputValidator()
    result = v.validate("")
    assert result.valid is True
    assert len(result.code_blocks) == 0
