"""security.dependency_guard -- AI-generated-code trust gate (WP0).

USENIX Security 2025 (Spracklen et al.) measured 19.7% of AI-generated code
samples reference non-existent packages ("hallucinated"/"slopsquatted"
dependencies), with 43% of hallucinated names recurring deterministically --
attackers pre-register the names a model is likely to invent. DependencyGuard
extracts imports from a code snippet and classifies each against (a) the
project's own lockfiles (via core.sbom.parse_project_lockfiles) and (b) a
bundled offline popular-package list, for two purposes:

  - typosquat/name-confusion detection (edit-distance <=2 to a popular name)
  - "not locked, not popular" flagging as a hallucination candidate

An optional allow_network=True path additionally checks PyPI for outright
nonexistent names. Offline by default -- air-gap safe, same posture as
SecurityScanner._check_osv.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_PY_IMPORT_RE = re.compile(r'(?m)^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)')
_JS_IMPORT_RE = re.compile(
    r'''require\(\s*['"]([^'"./][^'"]*)['"]\s*\)'''
    r'''|import\s+(?:[\w{}\s,*]+\s+from\s+)?['"]([^'"./][^'"]*)['"]'''
)

# Python 3.12 stdlib top-level module names commonly seen in AI-generated
# snippets -- excluded so a plain `import os` never counts as a dependency.
# Not exhaustive; extend as false positives surface.
_STDLIB_SKIP = {
    "os", "sys", "re", "json", "typing", "pathlib", "dataclasses", "asyncio",
    "itertools", "functools", "collections", "math", "time", "uuid",
    "subprocess", "urllib", "logging", "abc", "enum", "io", "copy", "hashlib",
    "secrets", "tempfile", "unittest", "argparse", "threading", "socket",
    "struct", "shutil", "glob", "csv", "datetime", "random", "string",
    "textwrap", "traceback", "warnings", "weakref", "contextlib", "inspect",
    "operator", "queue", "signal", "sqlite3", "statistics", "zipfile",
}

_POPULAR_PACKAGES_PATH = Path(__file__).resolve().parents[3] / "corpus" / "popular_packages.json"


@dataclass(frozen=True)
class DependencyFinding:
    name: str
    verdict: str  # "known" | "unknown_to_lockfile" | "suspect_confusion" | "registry_missing"
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "verdict": self.verdict, "detail": self.detail}


def _load_popular_packages(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    names = data.get("packages", []) if isinstance(data, dict) else data
    return [str(n).lower() for n in names] if isinstance(names, list) else []


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


class DependencyGuard:
    def __init__(self, popular_packages_path: "Path | None" = None):
        self._popular = _load_popular_packages(popular_packages_path or _POPULAR_PACKAGES_PATH)

    def extract_imports(self, code: str) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()

        for m in _PY_IMPORT_RE.finditer(code):
            top = m.group(1).split(".")[0]
            if top in _STDLIB_SKIP or top in seen:
                continue
            seen.add(top)
            names.append(top)

        for m in _JS_IMPORT_RE.finditer(code):
            raw = m.group(1) or m.group(2)
            if not raw:
                continue
            pkg = "/".join(raw.split("/")[:2]) if raw.startswith("@") else raw.split("/")[0]
            if pkg in seen:
                continue
            seen.add(pkg)
            names.append(pkg)

        return names

    def check(self, code: str, *, project_dir: "Path | None" = None,
              allow_network: bool = False) -> list[DependencyFinding]:
        locked: set[str] = set()
        if project_dir is not None:
            from promptwise.core.sbom import parse_project_lockfiles
            locked = {c["name"].lower() for c in parse_project_lockfiles(Path(project_dir))}

        return [self._verdict(name, locked, allow_network=allow_network)
                for name in self.extract_imports(code)]

    def _verdict(self, name: str, locked: set[str], *, allow_network: bool) -> DependencyFinding:
        lname = name.lower()
        if lname in locked or lname in self._popular:
            return DependencyFinding(name, "known",
                                      "present in project lockfile/manifest or bundled popular-package list")

        confusable = self._find_confusion(lname)
        if confusable:
            return DependencyFinding(name, "suspect_confusion",
                                      f"edit-distance <=2 to popular package '{confusable}' -- possible typosquat")

        if allow_network and not self._registry_has_package(lname):
            return DependencyFinding(name, "registry_missing",
                                      "not found on PyPI JSON API -- likely hallucinated package name")

        return DependencyFinding(name, "unknown_to_lockfile",
                                  "imported but not present in any parsed lockfile/manifest")

    def _find_confusion(self, lname: str) -> "str | None":
        # Length-gated: below 5 chars, ordinary short local module names
        # ('db', 'app', 'core', 'lib', 'src') collide with short corpus
        # entries ('pg', 'pip', 'cors', 'six') under an unscaled edit-distance
        # <=2 check, reaching a blocking hook path on plain code. No confusion
        # check at all below 5 chars; 5-7 chars requires distance <=1;
        # 8+ chars keeps the original distance <=2 tolerance.
        if len(lname) < 5:
            return None
        threshold = 1 if len(lname) <= 7 else 2
        for pop in self._popular:
            if len(pop) < 5:
                continue
            if abs(len(pop) - len(lname)) > 2:
                continue
            if _levenshtein(lname, pop) <= threshold:
                return pop
        return None

    def _registry_has_package(self, lname: str) -> bool:
        try:
            req = urllib.request.Request(f"https://pypi.org/pypi/{lname}/json")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            return True  # non-404 HTTP error (5xx, rate limit) — not evidence of hallucination
        except Exception:
            return True  # network unreachable/timeout — fail open, never fabricate a verdict
