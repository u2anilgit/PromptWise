import re
from dataclasses import dataclass, field


@dataclass
class ValidationIssue:
    severity: str
    message: str
    line: int | None = None
    code_snippet: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    issues: list[ValidationIssue]
    warnings: list[str]
    code_blocks: list[dict]
    languages_detected: list[str]
    has_imports: bool
    is_complete: bool


class CodexOutputValidator:
    CODE_BLOCK = r"```(\w+)\s*\n([\s\S]*?)\n\s*```"
    INCOMPLETE = [
        (r"def\s+\w+\s*\([^)]*\):\s*$", "Function definition missing body"),
        (r"class\s+\w+.*?:\s*$", "Class definition missing body"),
        (r"if\s+.*?:\s*$", "If statement missing body"),
        (r"for\s+.*?:\s*$", "For loop missing body"),
        (r"while\s+.*?:\s*$", "While loop missing body"),
        (r"try:\s*$", "Try block missing body"),
    ]
    SYNTAX = {
        "python": [(r"^\s*def\s+", "function"), (r"^\s*class\s+", "class"), (r"^\s*import\s+", "import"), (r"^\s*from\s+.*\s+import\s+", "from-import")],
        "javascript": [(r"function\s+\w+\s*\(", "function"), (r"const\s+\w+\s*=", "const"), (r"let\s+\w+\s*=", "let")],
        "typescript": [(r"function\s+\w+\s*\(", "function"), (r"interface\s+\w+", "interface"), (r"type\s+\w+\s*=", "type")],
        "sql": [(r"SELECT\s+", "SELECT"), (r"INSERT\s+INTO\s+", "INSERT"), (r"UPDATE\s+", "UPDATE")],
    }

    def validate(self, output: str) -> ValidationResult:
        issues: list[ValidationIssue] = []
        warnings: list[str] = []
        code_blocks = self._extract_blocks(output)
        languages = [b["language"] for b in code_blocks]
        has_imports = False
        is_complete = True

        for i, block in enumerate(code_blocks):
            blk_issues = self._validate_block(block, i + 1)
            issues.extend(blk_issues)
            if self._has_imports(block["code"], block["language"]):
                has_imports = True
            if not self._is_complete(block["code"]):
                is_complete = False

        if not code_blocks:
            warnings.append("No code blocks found")

        susp = self._check_suspicious(output)
        issues.extend(susp)
        valid = not any(i.severity == "error" for i in issues)

        return ValidationResult(valid=valid, issues=issues, warnings=warnings, code_blocks=code_blocks,
                                languages_detected=languages, has_imports=has_imports, is_complete=is_complete)

    def _extract_blocks(self, output: str) -> list[dict]:
        return [{"language": m.group(1).lower(), "code": m.group(2).strip()} for m in re.finditer(self.CODE_BLOCK, output)]

    def _validate_block(self, block: dict, num: int) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        code, lang = block["code"], block["language"]
        if not code.strip():
            issues.append(ValidationIssue(severity="error", message=f"Code block {num} is empty"))
            return issues
        issues.extend(self._check_brackets(code))
        if lang in self.SYNTAX:
            issues.extend(self._check_syntax(code, lang))
        issues.extend(self._check_incomplete(code))
        return issues

    def _check_brackets(self, code: str) -> list[ValidationIssue]:
        issues = []
        for chars, label in [("()", "parentheses"), ("{}", "braces"), ("[]", "brackets")]:
            diff = code.count(chars[0]) - code.count(chars[1])
            if diff != 0:
                issues.append(ValidationIssue(severity="warning", message=f"Unbalanced {label}: {diff:+d}"))
        return issues

    def _check_syntax(self, code: str, lang: str) -> list[ValidationIssue]:
        found = set()
        for pattern, desc in self.SYNTAX[lang]:
            if re.search(pattern, code, re.MULTILINE):
                found.add(desc)
        if not found and len(code) > 20:
            return [ValidationIssue(severity="info", message=f"No clear {lang} syntax patterns detected")]
        return []

    def _check_incomplete(self, code: str) -> list[ValidationIssue]:
        issues = []
        lines = code.split("\n")
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue
            for pattern, msg in self.INCOMPLETE:
                if re.search(pattern, stripped):
                    has_body = any(nxt.startswith((" ", "\t")) for nxt in lines[idx + 1:] if nxt.strip() and not nxt.strip().startswith(("#", "//")))
                    if not has_body:
                        issues.append(ValidationIssue(severity="warning", message=msg, line=idx + 1, code_snippet=line))
        return issues

    def _check_suspicious(self, output: str) -> list[ValidationIssue]:
        issues = []
        if "TODO" in output or "FIXME" in output:
            issues.append(ValidationIssue(severity="warning", message="Output contains TODO/FIXME comments"))
        if "..." in output or "[...]" in output:
            issues.append(ValidationIssue(severity="warning", message="Output contains placeholder patterns (...)"))
        return issues

    def _has_imports(self, code: str, lang: str) -> bool:
        if lang == "python":
            return bool(re.search(r"^\s*(import|from)\s+", code, re.MULTILINE))
        if lang in ("javascript", "typescript"):
            return bool(re.search(r"^\s*(import|require|from)\s+", code, re.MULTILINE))
        return False

    def _is_complete(self, code: str) -> bool:
        for pattern, _ in self.INCOMPLETE:
            if re.search(pattern, code):
                return False
        return not (code.count("(") != code.count(")") or code.count("{") != code.count("}") or code.count("[") != code.count("]"))
