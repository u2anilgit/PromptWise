"""WP0 -- dependency-hallucination ("slopsquatting") trust gate.

security.dependency_guard.DependencyGuard extracts imports from a code
snippet and classifies each against the project's own lockfiles (reusing
core.sbom.parse_project_lockfiles) and a bundled offline popular-package
list, flagging typosquat-confusable and (optionally, online) nonexistent
package names.
"""
import urllib.error

import pytest

from promptwise.security.dependency_guard import DependencyGuard

G = DependencyGuard()


def test_extract_python_imports():
    code = "import requests\nfrom flask import Flask\nimport os, sys\nfrom . import helper\n"
    names = G.extract_imports(code)
    assert "requests" in names
    assert "flask" in names
    assert "os" not in names  # stdlib excluded
    assert "sys" not in names  # stdlib excluded
    assert "helper" not in names  # relative import excluded


def test_extract_python_imports_submodule_collapses_to_top_level():
    names = G.extract_imports("import boto3.session\nfrom sklearn.linear_model import LogisticRegression\n")
    assert names == ["boto3", "sklearn"]


def test_extract_js_requires_and_imports():
    code = 'const axios = require("axios");\nimport React from "react";\nimport "./local-style.css";\n'
    names = G.extract_imports(code)
    assert "axios" in names
    assert "react" in names
    assert "./local-style.css" not in names


def test_extract_imports_dedupes_preserving_first_order():
    names = G.extract_imports("import requests\nimport flask\nimport requests\n")
    assert names == ["requests", "flask"]


def _verdicts(findings):
    return {f.name: f.verdict for f in findings}


def test_known_popular_package_without_project_dir_is_known():
    findings = DependencyGuard().check("import requests\n")
    assert _verdicts(findings) == {"requests": "known"}


def test_package_present_in_project_lockfile_is_known(tmp_path):
    (tmp_path / "requirements.txt").write_text("obscure-internal-pkg==1.0.0\n", encoding="utf-8")
    findings = DependencyGuard().check("import obscure_internal_pkg\n", project_dir=tmp_path)
    # underscore-vs-hyphen: lockfile has 'obscure-internal-pkg', import is
    # 'obscure_internal_pkg' -- exact string match only, no normalization,
    # so this one is NOT known; prove the true-known path with a matching name.
    assert _verdicts(findings)["obscure_internal_pkg"] != "known"

    (tmp_path / "requirements.txt").write_text("obscure_internal_pkg==1.0.0\n", encoding="utf-8")
    findings = DependencyGuard().check("import obscure_internal_pkg\n", project_dir=tmp_path)
    assert _verdicts(findings)["obscure_internal_pkg"] == "known"


def test_typosquat_confusable_flagged():
    # 'reqeusts' is a transposition of 'requests' -- edit distance 2.
    findings = DependencyGuard().check("import reqeusts\n")
    f = findings[0]
    assert f.verdict == "suspect_confusion"
    assert "requests" in f.detail


def test_unrelated_unlocked_import_is_unknown_to_lockfile():
    findings = DependencyGuard().check("import totally_made_up_internal_thing_xyz\n")
    assert findings[0].verdict == "unknown_to_lockfile"


def test_allow_network_false_never_calls_urlopen(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("network access attempted with allow_network=False")
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    findings = DependencyGuard().check("import totally_made_up_internal_thing_xyz\n", allow_network=False)
    assert findings[0].verdict == "unknown_to_lockfile"


def test_allow_network_true_registry_missing_on_404(monkeypatch):
    def _raise_404(*a, **k):
        raise urllib.error.HTTPError("https://pypi.org/pypi/x/json", 404, "Not Found", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", _raise_404)
    findings = DependencyGuard().check("import totally_made_up_internal_thing_xyz\n", allow_network=True)
    assert findings[0].verdict == "registry_missing"


def test_allow_network_true_fails_open_on_timeout(monkeypatch):
    def _timeout(*a, **k):
        raise TimeoutError("simulated network timeout")
    monkeypatch.setattr(urllib.request, "urlopen", _timeout)
    findings = DependencyGuard().check("import totally_made_up_internal_thing_xyz\n", allow_network=True)
    # a network hiccup must never manufacture a "registry_missing" verdict
    assert findings[0].verdict == "unknown_to_lockfile"


from promptwise.security.scanner import SecurityScanner


def test_scanner_check_dependency_trust_delegates_to_guard():
    vulns = SecurityScanner().check_dependency_trust("import reqeusts\n")
    assert vulns[0]["name"] == "reqeusts"
    assert vulns[0]["verdict"] == "suspect_confusion"


def test_security_check_flags_typosquat_import():
    result = SecurityScanner().check("import reqeusts\nprint('hello')\n")
    dep_violations = [v for v in result.violations if v["check"] == "dependencies"]
    assert len(dep_violations) == 1
    assert "reqeusts" in dep_violations[0]["detail"]


def test_security_check_does_not_flag_known_popular_import():
    result = SecurityScanner().check("import requests\nprint('hello')\n")
    assert not [v for v in result.violations if v["check"] == "dependencies"]


def test_security_check_does_not_flag_merely_unlocked_import():
    # Without a project_dir, an unrecognized-but-not-confusable name is
    # informational only (unknown_to_lockfile) -- it must not spam every
    # security_check call for legitimate lesser-known packages.
    result = SecurityScanner().check("import some_niche_but_legit_lib\n")
    assert not [v for v in result.violations if v["check"] == "dependencies"]


import asyncio
import json
import typing

from promptwise import server as srv


class _Ctx:
    pass


def _call(name, arguments):
    ctx = typing.cast(srv.ServerContext, _Ctx())
    coro = typing.cast("typing.Coroutine[typing.Any, typing.Any, str]", srv._HANDLERS[name](ctx, arguments))
    return asyncio.run(coro)


def test_validate_dependencies_handler_flags_typosquat():
    out = json.loads(_call("validate_dependencies", {"code": "import reqeusts\n"}))
    assert set(out) == {"dependencies", "suspect_count", "passed"}
    assert out["passed"] is False
    assert out["suspect_count"] == 1
    assert out["dependencies"][0]["verdict"] == "suspect_confusion"


def test_validate_dependencies_handler_passes_on_known_import():
    out = json.loads(_call("validate_dependencies", {"code": "import requests\n"}))
    assert out["passed"] is True
    assert out["suspect_count"] == 0


def test_validate_dependencies_handler_honors_project_dir(tmp_path):
    (tmp_path / "requirements.txt").write_text("obscure_internal_pkg==1.0.0\n", encoding="utf-8")
    out = json.loads(_call("validate_dependencies", {
        "code": "import obscure_internal_pkg\n",
        "project_dir": str(tmp_path),
    }))
    assert out["dependencies"][0]["verdict"] == "known"


def test_validate_dependencies_handler_default_allow_network_false(monkeypatch):
    import urllib.request

    def _boom(*a, **k):
        raise AssertionError("network access attempted with allow_network unset")
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    out = json.loads(_call("validate_dependencies", {"code": "import totally_made_up_internal_thing_xyz\n"}))
    assert out["dependencies"][0]["verdict"] == "unknown_to_lockfile"
