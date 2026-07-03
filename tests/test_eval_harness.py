"""Phase 7 WP7.3 — durable eval + regression harness.

Acceptance (docs/PHASE7_ROADMAP.md §7.3):
- A case with a known-good baseline passes (no regression flagged).
- A deliberately regressed output is flagged by the baseline diff / gate.
- Runs fully offline with no cloud dependency (record mode or injected local
  runtime) — never touches the network.
- Eval outcomes feed the 7.1 outcome store, closing the learning loop.
"""
import json

import pytest

from promptwise.core.adaptive_router import OutcomeStore
from promptwise.core.eval_harness import (
    EvalCase,
    EvalHarness,
    EvalResultStore,
    load_cases,
)


# ── fixtures / helpers ───────────────────────────────────────────────────────
def _good(prompt, tier):
    return "The capital of France is Paris. A complete, correct answer."


def _regressed(prompt, tier):
    # Missing the expected term entirely -> scores below the bar -> not_met.
    return "Sorry, no idea."


def _case():
    return EvalCase(id="qa-capital", prompt="Capital of France?",
                    task_class="qa/low", tier="fast", expect_contains=["Paris"])


def _stores(tmp_path):
    return (OutcomeStore(tmp_path / "outcomes.db"),
            EvalResultStore(tmp_path / "evals.db"))


# ── case format / loading ────────────────────────────────────────────────────
def test_load_cases_from_json_file(tmp_path):
    p = tmp_path / "suite.json"
    p.write_text(json.dumps({"cases": [
        {"id": "c1", "prompt": "hi", "task_class": "qa/low", "tier": "fast",
         "expect_contains": ["hello"]},
    ]}), encoding="utf-8")
    cases = load_cases(p)
    assert len(cases) == 1
    assert cases[0].id == "c1"
    assert cases[0].expect_contains == ["hello"]


def test_load_cases_from_directory(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(
        {"id": "a", "prompt": "x", "task_class": "t"}), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(
        [{"id": "b", "prompt": "y", "task_class": "t"}]), encoding="utf-8")
    cases = load_cases(tmp_path)
    assert {c.id for c in cases} == {"a", "b"}


# ── scoring reuses the existing quality logic ────────────────────────────────
def test_score_meets_bar_for_good_output(tmp_path):
    _, rstore = _stores(tmp_path)
    h = EvalHarness(result_store=rstore)
    score, verdict, _ = h.score(_case(), _good("", "fast"))
    assert verdict == "met"
    assert score >= 0.6


def test_score_below_bar_for_regressed_output(tmp_path):
    _, rstore = _stores(tmp_path)
    h = EvalHarness(result_store=rstore)
    score, verdict, signals = h.score(_case(), _regressed("", "fast"))
    assert verdict == "not_met"
    assert any("Paris" in s for s in signals)


# ── acceptance: known-good baseline passes (no regression) ───────────────────
def test_known_good_baseline_passes(tmp_path):
    ostore, rstore = _stores(tmp_path)
    h = EvalHarness(runner=_good, outcome_store=ostore, result_store=rstore)
    first = h.run([_case()])
    h.save_baseline(first)
    again = h.run([_case()])
    assert again.gate == "pass"
    assert again.regressions == []


# ── acceptance: a regressed output is flagged by the baseline gate ───────────
def test_regressed_output_is_flagged(tmp_path):
    ostore, rstore = _stores(tmp_path)
    good = EvalHarness(runner=_good, outcome_store=ostore, result_store=rstore)
    good.save_baseline(good.run([_case()]))

    bad = EvalHarness(runner=_regressed, outcome_store=ostore, result_store=rstore)
    run = bad.run([_case()])
    assert run.gate == "fail"
    assert any(r.case_id == "qa-capital" for r in run.regressions)


def test_no_baseline_means_no_regression(tmp_path):
    ostore, rstore = _stores(tmp_path)
    # Even a weak output is not a *regression* when there is no baseline to beat.
    run = EvalHarness(runner=_regressed, outcome_store=ostore,
                      result_store=rstore).run([_case()])
    assert run.regressions == []
    assert run.gate == "pass"


# ── acceptance: fully offline, no cloud dependency ───────────────────────────
def test_runs_offline_in_record_mode(tmp_path, monkeypatch):
    # Prove the offline default never reaches for the network: make any socket /
    # urlopen call explode, then run with no runner (record/dry-run mode).
    import urllib.request

    def _boom(*a, **k):
        raise AssertionError("network access attempted during offline eval")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    ostore, rstore = _stores(tmp_path)
    run = EvalHarness(runner=None, outcome_store=ostore, result_store=rstore).run([_case()])
    assert run.mode == "record"
    assert len(run.results) == 1
    assert run.results[0].mode == "record"


def test_injected_local_runtime_is_used_when_available(tmp_path):
    ostore, rstore = _stores(tmp_path)
    h = EvalHarness(runner=_good, outcome_store=ostore, result_store=rstore)
    run = h.run([_case()])
    assert run.mode == "local"
    assert "Paris" in run.results[0].output


# ── acceptance: closes the loop into the 7.1 outcome store ───────────────────
def test_outcomes_written_to_71_store(tmp_path):
    ostore, rstore = _stores(tmp_path)
    h = EvalHarness(runner=_good, outcome_store=ostore, result_store=rstore)
    h.run([_case()])
    stats = ostore.stats("qa/low")
    assert stats, "outcome store received no record"
    fast = stats["fast"]
    assert fast["met"] + fast["not_met"] + fast["neutral"] >= 1
    assert fast["met"] >= 1  # good output was recorded as 'met'


def test_regressed_outcome_recorded_as_not_met(tmp_path):
    ostore, rstore = _stores(tmp_path)
    EvalHarness(runner=_regressed, outcome_store=ostore, result_store=rstore).run([_case()])
    assert ostore.stats("qa/low")["fast"]["not_met"] >= 1


# ── result store round-trips + tier dimension ────────────────────────────────
def test_results_persisted_and_readable(tmp_path):
    ostore, rstore = _stores(tmp_path)
    EvalHarness(runner=_good, outcome_store=ostore, result_store=rstore,
                suite="s1").run([_case()])
    rows = rstore.results("s1")
    assert len(rows) == 1
    assert rows[0]["case_id"] == "qa-capital"
    assert rows[0]["verdict"] == "met"


def test_run_across_multiple_tiers(tmp_path):
    ostore, rstore = _stores(tmp_path)
    run = EvalHarness(runner=_good, outcome_store=ostore, result_store=rstore).run(
        [_case()], tiers=["fast", "balanced"])
    assert {r.tier for r in run.results} == {"fast", "balanced"}


def test_baseline_is_per_tier(tmp_path):
    ostore, rstore = _stores(tmp_path)
    h = EvalHarness(runner=_good, outcome_store=ostore, result_store=rstore)
    h.save_baseline(h.run([_case()], tiers=["fast", "balanced"]))
    # regress only the 'fast' tier; 'balanced' stays good
    def _mixed(prompt, tier):
        return _regressed(prompt, tier) if tier == "fast" else _good(prompt, tier)
    run = EvalHarness(runner=_mixed, outcome_store=ostore, result_store=rstore).run(
        [_case()], tiers=["fast", "balanced"])
    assert run.gate == "fail"
    assert {r.tier for r in run.regressions} == {"fast"}
