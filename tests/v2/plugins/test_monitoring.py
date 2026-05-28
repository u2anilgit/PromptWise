import pytest
from promptwise_v2.plugins.monitoring import CostMonitor


def test_no_alert_under_threshold():
    monitor = CostMonitor(alert_threshold_usd_per_min=5.0)
    event = monitor.record_step(cost_usd=0.01, duration_ms=60000)
    assert event is None


def test_alert_over_threshold():
    monitor = CostMonitor(alert_threshold_usd_per_min=5.0)
    event = monitor.record_step(cost_usd=6.0, duration_ms=60000)
    assert event is not None
    assert event.plugin_name == "monitoring"
    assert "cost" in event.trigger.lower() or "overspend" in event.trigger.lower()


def test_energy_score_computed():
    monitor = CostMonitor(alert_threshold_usd_per_min=5.0)
    score = monitor.energy_efficiency_score(model="claude-haiku-4-5-20251001", tokens=1000)
    assert 0.0 <= score <= 1.0


def test_energy_score_haiku_better_than_opus():
    monitor = CostMonitor(alert_threshold_usd_per_min=5.0)
    haiku = monitor.energy_efficiency_score(model="claude-haiku-4-5-20251001", tokens=1000)
    opus = monitor.energy_efficiency_score(model="claude-opus-4-7", tokens=1000)
    assert haiku >= opus


def test_burn_rate_usd_per_min():
    monitor = CostMonitor(alert_threshold_usd_per_min=5.0)
    rate = monitor.burn_rate_usd_per_min(cost_usd=0.10, duration_ms=30000)
    assert rate == pytest.approx(0.20, rel=0.01)
