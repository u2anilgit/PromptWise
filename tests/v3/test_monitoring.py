"""Tests for CostMonitor."""

from promptwise_v3.plugins.monitoring import CostMonitor


def test_record_step_no_alert():
    m = CostMonitor(alert_threshold_usd_per_min=10.0)
    event = m.record_step(cost_usd=0.5, duration_ms=60000)
    assert event is None


def test_record_step_alert():
    m = CostMonitor(alert_threshold_usd_per_min=1.0)
    event = m.record_step(cost_usd=5.0, duration_ms=60000)
    assert event is not None
    assert event.plugin_name == "monitoring"


def test_burn_rate():
    m = CostMonitor()
    rate = m.burn_rate(cost_usd=1.0, duration_ms=60000)
    assert rate == 1.0


def test_energy_efficiency_score():
    m = CostMonitor()
    score = m.energy_efficiency_score(model="claude-sonnet-4-6")
    assert 0 <= score <= 1.0


def test_energy_efficiency_all_models():
    m = CostMonitor()
    for model in ("claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-7",
                  "gpt-4o", "gpt-4o-mini", "gemini-2.0-flash", "gemini-2.0-pro"):
        score = m.energy_efficiency_score(model=model)
        assert 0 <= score <= 1.0
