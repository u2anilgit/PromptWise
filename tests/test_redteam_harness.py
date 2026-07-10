"""Phase 11 WP11.3 — durable red-team harness.

Acceptance (mirrors eval_harness's contract for the security domain):
- Built-in corpus covers every target_check with an attack + benign pair.
- A case with a known-good baseline passes (no regression flagged).
- A scanner that stops catching a previously-caught attack is flagged by the
  baseline diff / gate (simulated via a monkeypatched scanner).
- Loading from a JSON file/dir works the same way eval_harness cases load.

Note: attack-side example text below is pulled from the module's own builtin
corpus (via id lookup) rather than retyped here, so this test file's source
never itself contains a contiguous attack-pattern substring.
"""
import dataclasses
import json

from promptwise.core.redteam_harness import (
    RedTeamCase,
    RedTeamHarness,
    RedTeamResult,
    RedTeamResultStore,
    builtin_cases,
    load_cases,
)
from promptwise.security.scanner import SecurityScanner

_CASES = {c.id: c for c in builtin_cases()}


def _case(target_check, expect_flag, case_id):
    c = _CASES[case_id]
    return RedTeamCase(id=case_id, input_text=c.input_text, target_check=target_check, expect_flag=expect_flag)


# ── built-in corpus / case model ─────────────────────────────────────────────
def test_builtin_cases_cover_every_target_check():
    cases = builtin_cases()
    by_check = {}
    for c in cases:
        by_check.setdefault(c.target_check, []).append(c)
    expected_checks = {"injection", "secrets", "destructive", "supply_chain", "permissions", "pii", "owasp"}
    assert set(by_check) == expected_checks
    for check, pair in by_check.items():
        flags = {c.expect_flag for c in pair}
        assert flags == {True, False}, f"{check} missing an attack/benign pair"


def test_load_cases_from_json_file(tmp_path):
    p = tmp_path / "suite.json"
    p.write_text(json.dumps({"cases": [
        {"id": "c1", "input_text": _CASES["rt-destructive-attack"].input_text,
         "target_check": "destructive", "expect_flag": True},
    ]}), encoding="utf-8")
    cases = load_cases(p)
    assert len(cases) == 1
    assert cases[0].id == "c1"
    assert cases[0].expect_flag is True


def test_load_cases_from_directory(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(
        {"id": "a", "input_text": "x", "target_check": "pii", "expect_flag": False}), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(
        [{"id": "b", "input_text": "y", "target_check": "pii", "expect_flag": False}]), encoding="utf-8")
    cases = load_cases(tmp_path)
    assert {c.id for c in cases} == {"a", "b"}


def test_case_round_trips_through_dict():
    c = RedTeamCase(id="x", input_text="t", target_check="pii", expect_flag=False, severity="low")
    assert RedTeamCase.from_dict(c.to_dict()).to_dict() == c.to_dict()


# ── result store ─────────────────────────────────────────────────────────────
def test_result_store_records_and_reads_back(tmp_path):
    store = RedTeamResultStore(tmp_path / "rt.db")
    r = RedTeamResult(case_id="c1", target_check="pii", expect_flag=True, flagged=True,
                      verdict="met", matched=["Found PII: email"], ts="2026-07-04T00:00:00Z")
    store.record_result(r, suite="s1")
    rows = store.results("s1")
    assert len(rows) == 1
    assert rows[0]["case_id"] == "c1"
    assert rows[0]["verdict"] == "met"


def test_baseline_round_trip(tmp_path):
    store = RedTeamResultStore(tmp_path / "rt.db")
    assert store.get_baseline("c1", "pii") is None
    store.save_baseline("c1", "pii", "met", suite="default", ts="2026-07-04T00:00:00Z")
    base = store.get_baseline("c1", "pii")
    assert base is not None
    assert base["verdict"] == "met"


# ── harness: verdicts against the real scanner ───────────────────────────────
def test_attack_case_is_caught(tmp_path):
    h = RedTeamHarness(result_store=RedTeamResultStore(tmp_path / "rt.db"))
    r = h.run_case(_case("destructive", True, "rt-destructive-attack"))
    assert r.flagged is True
    assert r.verdict == "met"


def test_benign_case_is_not_flagged(tmp_path):
    h = RedTeamHarness(result_store=RedTeamResultStore(tmp_path / "rt.db"))
    r = h.run_case(_case("destructive", False, "rt-destructive-benign"))
    assert r.flagged is False
    assert r.verdict == "met"


def test_owasp_target_check_uses_check_owasp(tmp_path):
    h = RedTeamHarness(result_store=RedTeamResultStore(tmp_path / "rt.db"))
    r = h.run_case(_case("owasp", True, "rt-owasp-attack"))
    assert r.flagged is True
    assert r.verdict == "met"


def test_full_builtin_corpus_passes_against_the_real_scanner(tmp_path):
    h = RedTeamHarness(result_store=RedTeamResultStore(tmp_path / "rt.db"))
    run = h.run(builtin_cases())
    not_met = [r for r in run.results if r.verdict == "not_met"]
    assert not_met == [], f"builtin corpus cases failing against the real scanner: {not_met}"


def test_known_good_baseline_passes(tmp_path):
    store = RedTeamResultStore(tmp_path / "rt.db")
    h = RedTeamHarness(result_store=store)
    first = h.run([_case("destructive", True, "rt-destructive-attack")])
    h.save_baseline(first)
    again = h.run([_case("destructive", True, "rt-destructive-attack")])
    assert again.gate == "pass"
    assert again.regressions == []


def test_scanner_regression_is_flagged(tmp_path):
    store = RedTeamResultStore(tmp_path / "rt.db")
    good = RedTeamHarness(scanner=SecurityScanner(), result_store=store)
    good.save_baseline(good.run([_case("destructive", True, "rt-destructive-attack")]))

    class _BlindScanner(SecurityScanner):
        def check(self, text, *, allow_network=False):
            r = super().check(text, allow_network=allow_network)
            kept = [v for v in r.violations if v["check"] != "destructive"]
            return dataclasses.replace(r, violations=kept, passed=not kept)

    blind = RedTeamHarness(scanner=_BlindScanner(), result_store=store)
    run = blind.run([_case("destructive", True, "rt-destructive-attack")])
    assert run.gate == "fail"
    assert any(r.case_id == "rt-destructive-attack" for r in run.regressions)
