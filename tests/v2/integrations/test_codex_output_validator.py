"""
Tests for Codex output validator.
"""

import pytest

from promptwise_v2.core.codex_output_validator import (
    CodexOutputValidator,
    ValidationResult,
    ValidationIssue
)


@pytest.fixture
def validator():
    """Create CodexOutputValidator instance."""
    return CodexOutputValidator()


class TestCodeBlockExtraction:
    """Test code block extraction."""

    def test_extract_single_python_block(self, validator):
        """Test extracting single Python code block."""
        output = """
        Here's the Python code:
        ```python
        def hello():
            print("Hello, World!")
        ```
        """

        blocks = validator._extract_code_blocks(output)

        assert len(blocks) == 1
        assert blocks[0]["language"] == "python"
        assert "def hello()" in blocks[0]["code"]

    def test_extract_multiple_blocks(self, validator):
        """Test extracting multiple code blocks."""
        output = """
        ```python
        x = 1
        ```

        ```javascript
        const y = 2;
        ```
        """

        blocks = validator._extract_code_blocks(output)

        assert len(blocks) == 2
        assert blocks[0]["language"] == "python"
        assert blocks[1]["language"] == "javascript"

    def test_extract_no_blocks(self, validator):
        """Test when no code blocks present."""
        output = "This is just plain text with no code blocks."

        blocks = validator._extract_code_blocks(output)

        assert len(blocks) == 0

    def test_extract_case_insensitive_language(self, validator):
        """Test language names are normalized."""
        output = "```PYTHON\nprint('test')\n```"

        blocks = validator._extract_code_blocks(output)

        assert blocks[0]["language"] == "python"


class TestValidationResult:
    """Test validation result."""

    def test_validate_valid_python_code(self, validator):
        """Test validation of valid Python code."""
        output = """
        ```python
        def hello():
            print("Hello!")
        ```
        """

        result = validator.validate(output)

        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert len(result.code_blocks) == 1
        assert "python" in result.languages_detected

    def test_validate_no_code_blocks(self, validator):
        """Test validation with no code blocks."""
        output = "This is plain text."

        result = validator.validate(output)

        assert len(result.code_blocks) == 0
        assert len(result.warnings) > 0

    def test_validate_empty_code_block(self, validator):
        """Test validation of empty code block."""
        output = "```python\n\n```"

        result = validator.validate(output)

        # Should have errors for empty block
        assert len(result.issues) > 0


class TestBracketBalancing:
    """Test bracket balancing checks."""

    def test_balanced_brackets(self, validator):
        """Test code with balanced brackets."""
        block = {"language": "python", "code": "def func(a, b):\n    return a + b"}

        issues = validator._check_brackets(block["code"])

        # Should be valid
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_unbalanced_parentheses(self, validator):
        """Test unbalanced parentheses detection."""
        code = "def func(a, b:\n    pass"

        issues = validator._check_brackets(code)

        warnings = [i for i in issues if "parentheses" in i.message.lower()]
        assert len(warnings) > 0

    def test_unbalanced_braces(self, validator):
        """Test unbalanced braces detection."""
        code = "{ x: 1, y: 2"

        issues = validator._check_brackets(code)

        warnings = [i for i in issues if "braces" in i.message.lower()]
        assert len(warnings) > 0


class TestIncompletePatterns:
    """Test detection of incomplete code patterns."""

    def test_function_without_body(self, validator):
        """Test detecting function without body."""
        code = """
def calculate_total(items):
"""

        issues = validator._check_incomplete_patterns(code)

        assert len(issues) > 0
        assert any("Function definition" in i.message for i in issues)

    def test_class_without_body(self, validator):
        """Test detecting class without body."""
        code = """
class DataProcessor:
"""

        issues = validator._check_incomplete_patterns(code)

        assert len(issues) > 0

    def test_if_statement_without_body(self, validator):
        """Test detecting if without body."""
        code = """
if x > 5:
"""

        issues = validator._check_incomplete_patterns(code)

        assert len(issues) > 0

    def test_complete_function(self, validator):
        """Test complete function has no incomplete issues."""
        code = """
def greet(name):
    print(f"Hello, {name}")
"""

        issues = validator._check_incomplete_patterns(code)

        incomplete_issues = [i for i in issues if "missing body" in i.message.lower()]
        assert len(incomplete_issues) == 0


class TestSyntaxChecks:
    """Test language-specific syntax checks."""

    def test_python_syntax_detected(self, validator):
        """Test Python syntax detection."""
        code = """
import os
from typing import List

def process_files(files: List[str]):
    for file in files:
        print(file)
"""

        issues = validator._check_syntax(code, "python")

        # Should not complain about missing syntax
        info_issues = [i for i in issues if i.severity == "info"]
        assert len(info_issues) == 0

    def test_javascript_function_detected(self, validator):
        """Test JavaScript function detection."""
        code = """
function calculateSum(a, b) {
    return a + b;
}
"""

        issues = validator._check_syntax(code, "javascript")

        info_issues = [i for i in issues if i.severity == "info"]
        assert len(info_issues) == 0

    def test_sql_select_detected(self, validator):
        """Test SQL SELECT detection."""
        code = "SELECT * FROM users WHERE age > 18;"

        issues = validator._check_syntax(code, "sql")

        info_issues = [i for i in issues if i.severity == "info"]
        assert len(info_issues) == 0


class TestImportDetection:
    """Test import/require detection."""

    def test_python_import_detected(self, validator):
        """Test Python import detection."""
        code = "import os\nfrom typing import List"

        has_imports = validator._has_imports(code, "python")

        assert has_imports is True

    def test_javascript_import_detected(self, validator):
        """Test JavaScript import detection."""
        code = "import axios from 'axios';"

        has_imports = validator._has_imports(code, "javascript")

        assert has_imports is True

    def test_no_imports(self, validator):
        """Test code without imports."""
        code = "x = 1 + 2"

        has_imports = validator._has_imports(code, "python")

        assert has_imports is False


class TestCompleteness:
    """Test code completeness heuristic."""

    def test_complete_code(self, validator):
        """Test detection of complete code."""
        code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""

        is_complete = validator._is_complete(code)

        assert is_complete is True

    def test_incomplete_code(self, validator):
        """Test detection of incomplete code."""
        code = "def incomplete():"

        is_complete = validator._is_complete(code)

        assert is_complete is False

    def test_unmatched_brackets_incomplete(self, validator):
        """Test unmatched brackets mark as incomplete."""
        code = "func(a, b"

        is_complete = validator._is_complete(code)

        assert is_complete is False


class TestSuspiciousPatterns:
    """Test detection of suspicious patterns."""

    def test_todo_comment_detected(self, validator):
        """Test TODO comment detection."""
        output = "```python\n# TODO: implement this\npass\n```"

        issues = validator._check_suspicious_patterns(output)

        todo_issues = [i for i in issues if "TODO" in i.message]
        assert len(todo_issues) > 0

    def test_fixme_comment_detected(self, validator):
        """Test FIXME comment detection."""
        output = "# FIXME: bug here"

        issues = validator._check_suspicious_patterns(output)

        fixme_issues = [i for i in issues if "FIXME" in i.message]
        assert len(fixme_issues) > 0

    def test_placeholder_dots_detected(self, validator):
        """Test placeholder dots detection."""
        output = "def func():\n    ...\n    # implementation"

        issues = validator._check_suspicious_patterns(output)

        placeholder_issues = [i for i in issues if "placeholder" in i.message.lower()]
        assert len(placeholder_issues) > 0


class TestFullValidation:
    """Test full validation workflow."""

    def test_validate_complete_python(self, validator):
        """Test validation of complete Python code."""
        output = """
Here's a Python function:

```python
def calculate_average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)
```

This function calculates the average of a list of numbers.
"""

        result = validator.validate(output)

        assert result.valid is True
        assert len(result.issues) == 0
        assert len(result.code_blocks) == 1
        assert result.is_complete is True

    def test_validate_incomplete_code(self, validator):
        """Test validation detects incomplete code."""
        output = """
```python
def incomplete():
```
"""

        result = validator.validate(output)

        assert result.is_complete is False
        assert len(result.issues) > 0

    def test_validate_multiple_languages(self, validator):
        """Test validation with multiple languages."""
        output = """
```python
def hello():
    print("Hello")
```

```javascript
function sayHi() {
    console.log("Hi");
}
```
"""

        result = validator.validate(output)

        assert len(result.code_blocks) == 2
        assert "python" in result.languages_detected
        assert "javascript" in result.languages_detected


class TestValidationResultFields:
    """Test ValidationResult fields."""

    def test_result_has_valid_field(self, validator):
        """Test result has valid field."""
        output = "```python\nprint('test')\n```"
        result = validator.validate(output)

        assert hasattr(result, 'valid')
        assert isinstance(result.valid, bool)

    def test_result_has_issues_list(self, validator):
        """Test result has issues list."""
        output = "No code here"
        result = validator.validate(output)

        assert hasattr(result, 'issues')
        assert isinstance(result.issues, list)

    def test_result_has_code_blocks(self, validator):
        """Test result has code_blocks list."""
        output = "```python\npass\n```"
        result = validator.validate(output)

        assert hasattr(result, 'code_blocks')
        assert isinstance(result.code_blocks, list)

    def test_result_has_languages_detected(self, validator):
        """Test result has languages_detected."""
        output = "```python\npass\n```"
        result = validator.validate(output)

        assert hasattr(result, 'languages_detected')
        assert isinstance(result.languages_detected, list)

    def test_result_has_completeness_flag(self, validator):
        """Test result has completeness flag."""
        output = "```python\ndef f():\n    pass\n```"
        result = validator.validate(output)

        assert hasattr(result, 'is_complete')
        assert isinstance(result.is_complete, bool)
