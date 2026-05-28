import ast
import re
from promptwise_v2.types_v2 import ValidationResult

_HALLUCINATED_PATTERNS = [
    re.compile(r'\bflask\.\w+_magic_\w+\b'),
    re.compile(r'\bnp\.super_\w+\b'),
    re.compile(r'\bpd\.magic_\w+\b'),
]

_STDLIB_MODULES = {
    "os", "sys", "re", "json", "pathlib", "typing", "dataclasses",
    "datetime", "collections", "itertools", "functools", "math",
    "asyncio", "threading", "subprocess", "tempfile", "shutil",
    "unittest", "logging", "time", "uuid", "hashlib", "base64",
}

_KNOWN_THIRD_PARTY = {
    "flask", "fastapi", "requests", "httpx", "pydantic", "sqlalchemy",
    "numpy", "pandas", "scipy", "sklearn", "torch", "tensorflow",
    "pytest", "yaml", "toml", "click", "typer", "rich", "aiohttp",
    "aiosqlite", "mcp", "anthropic", "openai",
}


class CodeValidator:
    def validate(self, code: str, language: str = "python") -> ValidationResult:
        if not code.strip():
            return ValidationResult(valid=True, issues=[], confidence=1.0,
                                    checks_run=["syntax", "imports", "api_patterns"])

        issues: list[dict] = []
        checks_run = ["syntax", "imports", "api_patterns"]

        if language == "python":
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                issues.append({"check": "syntax", "detail": str(e), "line": e.lineno})
                return ValidationResult(valid=False, issues=issues, confidence=0.0,
                                        checks_run=checks_run,
                                        suggested_fix="Fix syntax error before use")

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod = (node.names[0].name if isinstance(node, ast.Import)
                           else (node.module or ""))
                    top = mod.split(".")[0]
                    if top and top not in _STDLIB_MODULES and top not in _KNOWN_THIRD_PARTY:
                        issues.append({"check": "imports",
                                       "detail": f"unknown module: {top}",
                                       "line": node.lineno})

        for pattern in _HALLUCINATED_PATTERNS:
            if pattern.search(code):
                issues.append({"check": "api_patterns",
                                "detail": f"suspected hallucinated API: {pattern.pattern}"})

        confidence = max(0.0, 1.0 - len(issues) * 0.2)
        valid = all(i["check"] != "syntax" for i in issues)

        return ValidationResult(
            valid=valid,
            issues=issues,
            confidence=round(confidence, 3),
            checks_run=checks_run,
            suggested_fix="Review flagged imports and API calls" if issues else "",
        )
