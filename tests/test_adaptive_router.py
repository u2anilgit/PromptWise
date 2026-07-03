"""Phase 7 WP7.1 — adaptive routing that learns from outcome history.

Acceptance (docs/PHASE7_ROADMAP.md §7.1):
- No history -> routing identical to the static heuristic.
- Enough same-class outcomes meeting the bar at a cheaper tier -> route shifts
  cheaper for that class; a class that keeps failing at a cheap tier escalates.
- The scorer never routes below the configured floor and never selects a
  deprecated model.
- Any scorer error falls back to static routing (fail-open).
"""
import textwrap

from promptwise.core.adaptive_router import (
    AdaptiveRouter,
    OutcomeStore,
    normalize_quality_signal,
)
from promptwise.core.model_registry import ModelRegistry
from promptwise.core.router import Router

# ── a self-contained three-tier registry (no branded ids) ────────────────────
REG = textwrap.dedent("""
schema_version: 1
families:
  ff: { provider: testco, tier: fast }
  bf: { provider: testco, tier: balanced }
  pf: { provider: testco, tier: powerful }
models:
  - { alias: fast-cur, family: ff, status: current, release_date: "2026-01-01", price: {input_per_mtok: 1.0, output_per_mtok: 2.0} }
  - { alias: bal-cur, family: bf, status: current, release_date: "2026-01-01", price: {input_per_mtok: 3.0, output_per_mtok: 6.0} }
  - { alias: bal-old, family: bf, status: deprecated, release_date: "2099-01-01", price: {input_per_mtok: 3.0, output_per_mtok: 6.0} }
  - { alias: pow-cur, family: pf, status: current, release_date: "2026-01-01", price: {input_per_mtok: 10.0, output_per_mtok: 20.0} }
""")


def _registry(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(REG, encoding="utf-8")
    return ModelRegistry(p)


def _store(tmp_path):
    return OutcomeStore(tmp_path / "outcomes.db")


# ── quality-signal normalization ─────────────────────────────────────────────
def test_normalize_quality_signal_maps_existing_signals():
    # quality-gate verdicts
    assert normalize_quality_signal("PASS") == "met"
    assert normalize_quality_signal("WAIVED") == "met"
    assert normalize_quality_signal("FAIL") == "not_met"
    assert normalize_quality_signal("CONCERNS") == "neutral"
    # validate_output shapes
    assert normalize_quality_signal({"valid": True}) == "met"
    assert normalize_quality_signal({"valid": False}) == "not_met"
    assert normalize_quality_signal(True) == "met"
    assert normalize_quality_signal(False) == "not_met"
    # a captured correction is a failure signal
    assert normalize_quality_signal("correction") == "not_met"


def test_absence_of_signal_is_neutral_never_negative():
    assert normalize_quality_signal(None) == "neutral"
    assert normalize_quality_signal("") == "neutral"
    assert normalize_quality_signal("something-unknown") == "neutral"


# ── outcome store round-trips ────────────────────────────────────────────────
def test_outcome_store_records_and_aggregates(tmp_path):
    s = _store(tmp_path)
    for _ in range(3):
        s.record("code/high", "fast", quality_signal="PASS")
    s.record("code/high", "fast", quality_signal="FAIL")
    s.record("code/high", "fast", quality_signal="CONCERNS")  # neutral, not counted
    stats = s.stats("code/high")
    assert stats["fast"]["met"] == 3
    assert stats["fast"]["not_met"] == 1
    assert stats["fast"]["neutral"] == 1
    assert s.stats("other") == {}


# ── acceptance: no history == pure static ────────────────────────────────────
def test_no_history_keeps_static_tier(tmp_path):
    ar = AdaptiveRouter(store=_store(tmp_path))
    tier, reason = ar.adapt("code/high", "powerful")
    assert tier == "powerful"
    assert reason == ""


def test_router_with_empty_store_matches_static(tmp_path, monkeypatch):
    reg = _registry(tmp_path)
    ar = AdaptiveRouter(store=_store(tmp_path))
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_ROUTING", "on")
    r_on = Router(registry=reg, adaptive=ar)
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_ROUTING", "off")
    r_off = Router(registry=reg, adaptive=ar)
    for text, intent, stakes in [
        ("design a critical production architecture", "analysis", "high"),
        ("summarize this", "summarize", "low"),
        ("write a function", "code", "medium"),
    ]:
        a = r_on.route(text, intent=intent, stakes=stakes, provider="testco")
        b = r_off.route(text, intent=intent, stakes=stakes, provider="testco")
        assert a.recommended_model == b.recommended_model


# ── acceptance: cheaper tier that met the bar wins ───────────────────────────
def test_downgrades_to_cheaper_tier_after_enough_wins(tmp_path):
    store = _store(tmp_path)
    for _ in range(8):
        store.record("code/high", "fast", quality_signal="PASS")
    ar = AdaptiveRouter(store=store, min_samples=5)
    tier, reason = ar.adapt("code/high", "powerful")
    assert tier == "fast"
    assert "met the bar" in reason and "fast" in reason


def test_thin_history_does_not_downgrade(tmp_path):
    store = _store(tmp_path)
    for _ in range(3):  # below min_samples
        store.record("code/high", "fast", quality_signal="PASS")
    ar = AdaptiveRouter(store=store, min_samples=5)
    tier, _ = ar.adapt("code/high", "powerful")
    assert tier == "powerful"


def test_mixed_results_below_bar_do_not_downgrade(tmp_path):
    store = _store(tmp_path)
    for _ in range(3):
        store.record("code/high", "fast", quality_signal="PASS")
    for _ in range(3):
        store.record("code/high", "fast", quality_signal="FAIL")
    ar = AdaptiveRouter(store=store, min_samples=5)
    tier, _ = ar.adapt("code/high", "powerful")
    assert tier == "powerful"  # 50% met is below the bar


# ── acceptance: repeated failure at a cheap tier escalates ───────────────────
def test_escalates_when_cheap_tier_keeps_failing(tmp_path):
    store = _store(tmp_path)
    for _ in range(6):
        store.record("summarize/low", "fast", quality_signal="FAIL")
    ar = AdaptiveRouter(store=store, min_samples=5)
    tier, reason = ar.adapt("summarize/low", "fast")
    assert tier == "balanced"
    assert "escalated" in reason


def test_all_neutral_never_escalates(tmp_path):
    store = _store(tmp_path)
    for _ in range(6):
        store.record("summarize/low", "fast", quality_signal="CONCERNS")
    ar = AdaptiveRouter(store=store, min_samples=5)
    tier, reason = ar.adapt("summarize/low", "fast")
    assert tier == "fast"
    assert reason == ""


# ── acceptance: never routes below the floor ─────────────────────────────────
def test_never_routes_below_floor(tmp_path):
    store = _store(tmp_path)
    for _ in range(20):
        store.record("code/high", "fast", quality_signal="PASS")
    ar = AdaptiveRouter(store=store, min_samples=5, floor="balanced")
    tier, _ = ar.adapt("code/high", "powerful")
    # fast is below the floor -> never chosen despite strong evidence; with no
    # evidence at the floor tier the static pick is kept.
    assert tier != "fast"
    assert tier == "powerful"


def test_static_below_floor_is_raised_to_floor(tmp_path):
    ar = AdaptiveRouter(store=_store(tmp_path), floor="balanced")
    tier, _ = ar.adapt("summarize/low", "fast")
    assert tier == "balanced"


# ── acceptance: never selects a deprecated model ─────────────────────────────
def test_router_downgrade_never_selects_deprecated(tmp_path):
    reg = _registry(tmp_path)
    store = _store(tmp_path)
    # class historically meets the bar at the balanced tier
    for _ in range(8):
        store.record("analysis/high", "balanced", quality_signal="PASS")
    ar = AdaptiveRouter(store=store, min_samples=5)
    r = Router(registry=reg, adaptive=ar)
    res = r.route("design a critical production architecture",
                  intent="analysis", stakes="high", provider="testco")
    assert res.recommended_model == "bal-cur"       # downgraded from powerful
    assert res.recommended_model != "bal-old"       # deprecated never selected
    assert reg.is_deprecated("bal-old")


# ── acceptance: any scorer error falls back to static (fail-open) ────────────
def test_scorer_error_falls_back_to_static(tmp_path, monkeypatch):
    reg = _registry(tmp_path)

    class Boom(AdaptiveRouter):
        def adapt(self, *a, **k):
            raise RuntimeError("scorer exploded")

    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_ROUTING", "on")
    r = Router(registry=reg, adaptive=Boom(store=_store(tmp_path)))
    res = r.route("design a critical production architecture",
                  intent="analysis", stakes="high", provider="testco")
    assert res.recommended_model == "pow-cur"  # unchanged static pick, no crash


def test_env_flag_off_disables_adaptive(tmp_path, monkeypatch):
    reg = _registry(tmp_path)
    store = _store(tmp_path)
    for _ in range(8):
        store.record("analysis/high", "fast", quality_signal="PASS")
    ar = AdaptiveRouter(store=store, min_samples=5)
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_ROUTING", "off")
    r = Router(registry=reg, adaptive=ar)
    res = r.route("design a critical production architecture",
                  intent="analysis", stakes="high", provider="testco")
    assert res.recommended_model == "pow-cur"  # static, adaptive disabled


def test_router_reason_names_the_evidence(tmp_path, monkeypatch):
    reg = _registry(tmp_path)
    store = _store(tmp_path)
    for _ in range(8):
        store.record("analysis/high", "balanced", quality_signal="PASS")
    ar = AdaptiveRouter(store=store, min_samples=5)
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_ROUTING", "on")
    r = Router(registry=reg, adaptive=ar)
    res = r.route("design a critical production architecture",
                  intent="analysis", stakes="high", provider="testco")
    assert "met the bar" in res.reason
