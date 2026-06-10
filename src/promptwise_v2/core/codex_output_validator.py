"""
Codex 5.5 output validation.

Validates code-generation output from Codex 5.5 for:
- Valid code block format (```language ... ```)
- Syntax errors in common languages
- Required imports/modules
- Incomplete code patterns
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class ValidationIssue:
    """Represents a validation issue."""

    severity: str  # "error", "warning", "info"
    message: str
    line: Optional[int] = None
    code_snippet: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of code validation."""

    valid: bool
    issues: List[ValidationIssue]
    warnings: List[str]
    code_blocks: List[Dict[str, str]]
    languages_detected: List[str]
    has_imports: bool
    is_complete: bool


class CodexOutputValidator:
    """
    Validate Codex 5.5 code generation output.

    Checks for:
    - Code block format (triple backticks with language)
    - Syntax errors
    - Incomplete patterns (e.g., def without body)
    - Missing imports
    """

    # Pattern for code blocks: ```language\n code \n```
    CODE_BLOCK_PATTERN = r"```(\w+)\s*\n([\s\S]*?)\n\s*```"

    # Incomplete code patterns
    INCOMPLETE_PATTERNS = [
        (r"def\s+\w+\s*\([^)]*\):\s*$", "Function definition missing body"),
        (r"class\s+\w+.*?:\s*$", "Class definition missing body"),
        (r"if\s+.*?:\s*$", "If statement missing body"),
        (r"for\s+.*?:\s*$", "For loop missing body"),
        (r"while\s+.*?:\s*$", "While loop missing body"),
        (r"try:\s*$", "Try block missing body"),
        (r"except.*?:\s*$", "Except block missing body"),
    ]

    # Language-specific syntax checkers
    SYNTAX_PATTERNS = {
        "python": [
            (r"^\s*def\s+", "function definition"),
            (r"^\s*class\s+", "class definition"),
            (r"^\s*import\s+", "import statement"),
            (r"^\s*from\s+.*\s+import\s+", "from-import statement"),
        ],
        "javascript": [
            (r"function\s+\w+\s*\(", "function definition"),
            (r"const\s+\w+\s*=", "const declaration"),
            (r"let\s+\w+\s*=", "let declaration"),
            (r"var\s+\w+\s*=", "var declaration"),
        ],
        "typescript": [
            (r"function\s+\w+\s*\(", "function definition"),
            (r"interface\s+\w+", "interface definition"),
            (r"type\s+\w+\s*=", "type definition"),
        ],
        "sql": [
            (r"SELECT\s+", "SELECT statement"),
            (r"INSERT\s+INTO\s+", "INSERT statement"),
            (r"UPDATE\s+", "UPDATE statement"),
            (r"DELETE\s+FROM\s+", "DELETE statement"),
        ],
    }

    def __init__(self):
        """Initialize validator."""
        pass

    def validate(self, output: str) -> ValidationResult:
        """
        Validate Codex output.

        Args:
            output: Text output from Codex

        Returns:
            ValidationResult with issues and metrics
        """
        issues: List[ValidationIssue] = []
        warnings: List[str] = []
        code_blocks: List[Dict[str, str]] = []
        languages_detected: List[str] = []
        has_imports = False
        is_complete = True

        # Extract code blocks
        code_blocks = self._extract_code_blocks(output)
        if code_blocks:
            languages_detected = [b["language"] for b in code_blocks]

            # Validate each code block
            for i, block in enumerate(code_blocks):
                block_issues = self._validate_code_block(block, i + 1)
                issues.extend(block_issues)

                # Check for imports
                if self._has_imports(block["code"], block["language"]):
                    has_imports = True

                # Check for completeness
                if not self._is_complete(block["code"]):
                    is_complete = False

        else:
            warnings.append("No code blocks found in output")

        # Check for suspicious patterns
        suspicious_issues = self._check_suspicious_patterns(output)
        issues.extend(suspicious_issues)

        # Determine validity
        valid = not any(issue.severity == "error" for issue in issues)

        return ValidationResult(
            valid=valid,
            issues=issues,
            warnings=warnings,
            code_blocks=code_blocks,
            languages_detected=languages_detected,
            has_imports=has_imports,
            is_complete=is_complete
        )

    def _extract_code_blocks(self, output: str) -> List[Dict[str, str]]:
        """
        Extract code blocks from output.

        Args:
            output: Output text

        Returns:
            List of dicts: {language, code}
        """
        blocks = []
        matches = re.finditer(self.CODE_BLOCK_PATTERN, output)

        for match in matches:
            language = match.group(1).lower()
            code = match.group(2).strip()

            blocks.append({
                "language": language,
                "code": code
            })

        return blocks

    def _validate_code_block(self, block: Dict[str, str], block_num: int) -> List[ValidationIssue]:
        """
        Validate a single code block.

        Args:
            block: Code block dict
            block_num: Block number for error reporting

        Returns:
            List of ValidationIssue
        """
        issues: List[ValidationIssue] = []
        code = block["code"]
        language = block["language"]

        # Check for empty code blocks
        if not code.strip():
            issues.append(ValidationIssue(
                severity="error",
                message=f"Code block {block_num} is empty",
                code_snippet=""
            ))
            return issues

        # Check for balanced brackets
        bracket_issues = self._check_brackets(code)
        issues.extend(bracket_issues)

        # Language-specific checks
        if language in self.SYNTAX_PATTERNS:
            syntax_issues = self._check_syntax(code, language)
            issues.extend(syntax_issues)

        # Check for incomplete patterns
        incomplete_issues = self._check_incomplete_patterns(code)
        issues.extend(incomplete_issues)

        return issues

    def _check_brackets(self, code: str) -> List[ValidationIssue]:
        """
        Check for balanced brackets/quotes.

        Args:
            code: Code snippet

        Returns:
            List of ValidationIssue
        """
        issues: List[ValidationIssue] = []

        # Count brackets
        open_parens = code.count("(") - code.count(")")
        open_braces = code.count("{") - code.count("}")
        open_brackets = code.count("[") - code.count("]")

        if open_parens != 0:
            issues.append(ValidationIssue(
                severity="warning",
                message=f"Unbalanced parentheses: {open_parens:+d}"
            ))

        if open_braces != 0:
            issues.append(ValidationIssue(
                severity="warning",
                message=f"Unbalanced braces: {open_braces:+d}"
            ))

        if open_brackets != 0:
            issues.append(ValidationIssue(
                severity="warning",
                message=f"Unbalanced brackets: {open_brackets:+d}"
            ))

        return issues

    def _check_syntax(self, code: str, language: str) -> List[ValidationIssue]:
        """
        Check language-specific syntax.

        Args:
            code: Code snippet
            language: Programming language

        Returns:
            List of ValidationIssue
        """
        issues: List[ValidationIssue] = []

        if language not in self.SYNTAX_PATTERNS:
            return issues

        patterns = self.SYNTAX_PATTERNS[language]
        found_patterns = set()

        for pattern, description in patterns:
            if re.search(pattern, code, re.MULTILINE):
                found_patterns.add(description)

        # At least some structure expected in non-empty code
        if len(found_patterns) == 0 and language in ["python", "javascript", "sql"]:
            # Don't require structure for very short snippets
            if len(code) > 20:
                issues.append(ValidationIssue(
                    severity="info",
                    message=f"No clear {language} syntax patterns detected (may be incomplete)"
                ))

        return issues

    def _check_incomplete_patterns(self, code: str) -> List[ValidationIssue]:
        """
        Check for incomplete code patterns.

        Args:
            code: Code snippet

        Returns:
            List of ValidationIssue
        """
        issues: List[ValidationIssue] = []

        lines = code.split("\n")

        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines and comments
            if not line_stripped or line_stripped.startswith("#") or line_stripped.startswith("//"):
                continue

            for pattern, message in self.INCOMPLETE_PATTERNS:
                if re.search(pattern, line_stripped):
                    # Check if subsequent non-empty line is indented
                    has_body = False
                    for next_line in lines[line_idx + 1:]:
                        next_stripped = next_line.strip()
                        if next_stripped and not next_stripped.startswith("#") and not next_stripped.startswith("//"):
                            if next_line.startswith(" ") or next_line.startswith("\t"):
                                has_body = True
                            break

                    if not has_body:
                        issues.append(ValidationIssue(
                            severity="warning",
                            message=message,
                            line=line_idx + 1,
                            code_snippet=line
                        ))

        return issues

    def _check_suspicious_patterns(self, output: str) -> List[ValidationIssue]:
        """
        Check for suspicious patterns in output.

        Args:
            output: Full output text

        Returns:
            List of ValidationIssue
        """
        issues: List[ValidationIssue] = []

        # Check for "TODO" or "FIXME" comments (may indicate incomplete code)
        if "TODO" in output or "FIXME" in output:
            issues.append(ValidationIssue(
                severity="warning",
                message="Output contains TODO/FIXME comments (may be incomplete)"
            ))

        # Check for placeholder text
        if "..." in output or "[...]" in output:
            issues.append(ValidationIssue(
                severity="warning",
                message="Output contains placeholder patterns (...)"
            ))

        return issues

    def _has_imports(self, code: str, language: str) -> bool:
        """
        Check if code has imports.

        Args:
            code: Code snippet
            language: Programming language

        Returns:
            True if imports detected
        """
        if language == "python":
            return bool(re.search(r"^\s*(import|from)\s+", code, re.MULTILINE))

        elif language in ["javascript", "typescript"]:
            return bool(re.search(r"^\s*(import|require|from)\s+", code, re.MULTILINE))

        elif language == "sql":
            # SQL doesn't typically have imports
            return False

        return False

    def _is_complete(self, code: str) -> bool:
        """
        Heuristic check if code appears complete.

        Args:
            code: Code snippet

        Returns:
            True if code appears complete
        """
        # Check for unfinished patterns
        for pattern, _ in self.INCOMPLETE_PATTERNS:
            if re.search(pattern, code):
                return False

        # Check for unmatched brackets
        if (code.count("(") != code.count(")") or
            code.count("{") != code.count("}") or
            code.count("[") != code.count("]")):
            return False

        return True


__all__ = ["CodexOutputValidator", "ValidationResult", "ValidationIssue"]
