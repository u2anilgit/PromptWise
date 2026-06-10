"""Tests for CodeValidator."""

from promptwise_v3.plugins.code_validator import CodeValidator


def test_validate_valid_python():
    c = CodeValidator()
    result = c.validate("def hello():\n    print('hello')\n")
    assert result.valid is True
    assert len(result.issues) == 0


def test_validate_invalid_syntax():
    c = CodeValidator()
    result = c.validate("def hello(\n")
    assert result.valid is False
    assert len(result.issues) > 0


def test_validate_empty():
    c = CodeValidator()
    result = c.validate("")
    assert result.valid is True


def test_validate_hallucinated_api():
    c = CodeValidator()
    result = c.validate("import flask_magic\nflask_magic.super_optimize()")
    assert len(result.issues) > 0


def test_validate_stdlib():
    c = CodeValidator()
    result = c.validate("import os\nimport sys\nos.path.join('a', 'b')")
    assert result.valid is True
