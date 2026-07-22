"""effort_adapter -- reasoning-effort selection that learns from its own
outcome history, structurally mirroring adaptive_router.py's tests
(test_adaptive_router.py) but over EFFORT_ORDER instead of TIER_ORDER."""
from promptwise.core.effort_adapter import EffortAdapter, EffortOutcomeStore


def test_no_history_returns_static_effort_unchanged(tmp_path):
    store = EffortOutcomeStore(tmp_path / "eo.db")
    adapter = EffortAdapter(store=store)
    effort, reason = adapter.adapt("code/high", "high")
    assert effort == "high"
    assert reason == ""


def test_enough_met_samples_at_lower_effort_downgrades(tmp_path):
    store = EffortOutcomeStore(tmp_path / "eo.db")
    for _ in range(6):
        store.record("code/high", "medium", quality_signal="met")
    adapter = EffortAdapter(store=store, min_samples=5, meet_bar=0.7)
    effort, reason = adapter.adapt("code/high", "high")
    assert effort == "medium"
    assert "routed to lower effort" in reason


def test_repeated_failures_at_static_effort_escalate(tmp_path):
    store = EffortOutcomeStore(tmp_path / "eo.db")
    for _ in range(6):
        store.record("summarize/low", "low", quality_signal="not_met")
    adapter = EffortAdapter(store=store, min_samples=5, fail_bar=0.4)
    effort, reason = adapter.adapt("summarize/low", "low")
    assert effort == "medium"
    assert "escalated to 'medium'" in reason


def test_never_goes_below_configured_floor(tmp_path):
    store = EffortOutcomeStore(tmp_path / "eo.db")
    adapter = EffortAdapter(store=store, floor="medium")
    effort, _ = adapter.adapt("x/y", "low")
    assert effort == "medium"
