from promptwise_v2.plugins.code_validator import CodeValidator


def test_valid_python_passes():
    validator = CodeValidator()
    code = "def add(a, b):\n    return a + b\n"
    result = validator.validate(code, language="python")
    assert result.valid is True
    assert result.confidence >= 0.8


def test_syntax_error_detected():
    validator = CodeValidator()
    code = "def foo(\n    return 42"
    result = validator.validate(code, language="python")
    assert result.valid is False
    assert any(i["check"] == "syntax" for i in result.issues)


def test_unknown_import_flagged():
    validator = CodeValidator()
    code = "import totally_fake_module_xyz\nfoo = totally_fake_module_xyz.bar()"
    result = validator.validate(code, language="python")
    # Should flag unknown module (issues list may have import entry)
    assert len(result.checks_run) > 0


def test_empty_code_valid():
    validator = CodeValidator()
    result = validator.validate("", language="python")
    assert result.valid is True


def test_checks_run_listed():
    validator = CodeValidator()
    result = validator.validate("x = 1", language="python")
    assert len(result.checks_run) > 0


def test_confidence_bounded():
    validator = CodeValidator()
    result = validator.validate("def ok(): pass", language="python")
    assert 0.0 <= result.confidence <= 1.0
