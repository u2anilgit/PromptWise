"""static_analysis -- opt-in subprocess dispatch to a real linter (ruff for
python, eslint for js/ts).

Fail-open: if the linter binary isn't on PATH, or the run times out, this
returns tool_available=False and an empty issue list rather than raising --
see docs/superpowers/specs/2026-07-24-static-analysis-wiring-design.md.
Never uses shell=True; the code under analysis only ever becomes file
content, never a command-line argument, so it cannot inject shell commands.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_LANGUAGE_EXT = {"python": ".py", "javascript": ".js", "typescript": ".ts"}


@dataclass
class StaticAnalysisResult:
    tool_available: bool
    tool: str = ""
    issues: list[dict] = field(default_factory=list)


def _run_ruff(path: Path, timeout: float) -> list[dict]:
    proc = subprocess.run(
        ["ruff", "check", "--output-format=json", str(path)],
        capture_output=True, text=True, timeout=timeout,
    )
    if not proc.stdout.strip():
        return []
    findings = json.loads(proc.stdout)
    return [
        {
            "check": "static_analysis",
            "tool": "ruff",
            "detail": f"{f.get('code', '')}: {f.get('message', '')}".strip(": "),
            "line": (f.get("location") or {}).get("row"),
            "severity": "warning",
        }
        for f in findings
    ]


def _run_eslint(path: Path, timeout: float) -> list[dict]:
    proc = subprocess.run(
        ["eslint", "--format", "json", str(path)],
        capture_output=True, text=True, timeout=timeout,
    )
    if not proc.stdout.strip():
        return []
    results = json.loads(proc.stdout)
    out = []
    for file_result in results:
        for msg in file_result.get("messages", []):
            out.append({
                "check": "static_analysis",
                "tool": "eslint",
                "detail": msg.get("message", ""),
                "line": msg.get("line"),
                "severity": "error" if msg.get("severity") == 2 else "warning",
            })
    return out


def run_static_analysis(code: str, language: str = "python", timeout: float = 10.0) -> StaticAnalysisResult:
    ext = _LANGUAGE_EXT.get(language)
    if ext is None:
        return StaticAnalysisResult(tool_available=False)

    tool = "ruff" if language == "python" else "eslint"
    if shutil.which(tool) is None:
        return StaticAnalysisResult(tool_available=False, tool=tool)

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False, encoding="utf-8")
    try:
        tmp.write(code)
        tmp.close()
        path = Path(tmp.name)
        try:
            issues = _run_ruff(path, timeout) if tool == "ruff" else _run_eslint(path, timeout)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, OSError):
            return StaticAnalysisResult(tool_available=False, tool=tool)
        return StaticAnalysisResult(tool_available=True, tool=tool, issues=issues)
    finally:
        Path(tmp.name).unlink(missing_ok=True)
