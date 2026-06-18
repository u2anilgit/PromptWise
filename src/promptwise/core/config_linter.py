"""Linter for agent rules files (CLAUDE.md, AGENTS.md, .mdc, copilot-instructions).

Not a code linter. Mirrors the result shape of codex_validator.py.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LintIssue:
    severity: str  # "error" | "warning" | "info"
    message: str
    line: int | None = None


@dataclass
class LintResult:
    valid: bool  # False if any "error"
    issues: list[LintIssue]


# Frontmatter at the very start: ---\n ... \n---
FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
BLOAT_PHRASES = ("the architecture is", "this project is a", "directory structure")
LONG_LINE = 600
DUP_MIN_LEN = 40


class ConfigLinter:
    EXT_FMT = {
        ".md": "md",
        ".markdown": "md",
        ".mdc": "mdc",
        ".txt": "md",
    }

    def lint(self, content: str, *, fmt: str = "md", max_bytes: int | None = None,
             always_apply: bool = False, token_budget: int = 0) -> LintResult:
        issues: list[LintIssue] = []

        # 1. Byte cap
        size = len(content.encode("utf-8"))
        if max_bytes is not None and size > max_bytes:
            issues.append(LintIssue(severity="error",
                                    message=f"file exceeds max_bytes ({size} > {max_bytes})"))

        # 2. .mdc frontmatter
        fm = self._frontmatter(content)
        if fmt == "mdc":
            if fm is None or "description:" not in fm or not (
                "alwaysapply:" in fm.lower() or "globs:" in fm.lower()
            ):
                issues.append(LintIssue(
                    severity="error",
                    message="missing .mdc frontmatter (description/alwaysApply required)"))

        # frontmatter may declare alwaysApply: true
        fm_always = bool(fm and re.search(r"^\s*alwaysApply:\s*true\s*$", fm,
                                          re.MULTILINE | re.IGNORECASE))

        # 3. Always-apply token tax
        if (always_apply or fm_always) and token_budget > 0:
            est_tokens = len(content) // 4
            if est_tokens > token_budget:
                issues.append(LintIssue(
                    severity="warning",
                    message=(f"always-apply rules large (~{est_tokens} tokens > "
                             f"{token_budget}); Cursor charges this on every request")))

        # 4. Inferable bloat
        issues.extend(self._check_bloat(content))

        valid = not any(i.severity == "error" for i in issues)
        return LintResult(valid=valid, issues=issues)

    def lint_file(self, path: str | Path, **kw) -> LintResult:
        p = Path(path)
        if "fmt" not in kw:
            name = p.name.lower()
            if name.endswith(".mdc"):
                kw["fmt"] = "mdc"
            else:
                kw["fmt"] = self.EXT_FMT.get(p.suffix.lower(), "md")
        content = p.read_text(encoding="utf-8")
        return self.lint(content, **kw)

    def dedupe_check(self, files: dict[str, str]) -> list[LintIssue]:
        line_files: dict[str, set[str]] = {}
        for fname, content in files.items():
            seen: set[str] = set()
            for raw in content.splitlines():
                line = raw.strip()
                if len(line) <= DUP_MIN_LEN or line in seen:
                    continue
                seen.add(line)
                line_files.setdefault(line, set()).add(fname)

        issues: list[LintIssue] = []
        for line, fset in line_files.items():
            if len(fset) >= 2:
                issues.append(LintIssue(
                    severity="info",
                    message=f"line duplicated across {len(fset)} files"))
        return issues

    def _frontmatter(self, content: str) -> str | None:
        m = FRONTMATTER.match(content)
        return m.group(1) if m else None

    def _check_bloat(self, content: str) -> list[LintIssue]:
        issues: list[LintIssue] = []
        lower = content.lower()
        for idx, line in enumerate(content.splitlines(), start=1):
            if len(line) > LONG_LINE:
                issues.append(LintIssue(
                    severity="warning",
                    message="possible inferable bloat; prefer commands/rules over prose",
                    line=idx))
                return issues
        if any(p in lower for p in BLOAT_PHRASES) and len(content) > LONG_LINE:
            issues.append(LintIssue(
                severity="warning",
                message="possible inferable bloat; prefer commands/rules over prose"))
        return issues
