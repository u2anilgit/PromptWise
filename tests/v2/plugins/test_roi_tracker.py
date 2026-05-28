import pytest
from promptwise_v2.plugins.roi_tracker import ROITracker


def test_positive_roi_when_tokens_saved():
    tracker = ROITracker(dev_hourly_rate_usd=100.0)
    snap = tracker.calculate(
        session_id="s1", total_cost_usd=0.50,
        tokens_saved=50000, calls=20,
    )
    assert snap.roi_ratio > 1.0
    assert snap.estimated_time_saved_min > 0


def test_zero_cost_returns_nonnegative_roi():
    tracker = ROITracker(dev_hourly_rate_usd=100.0)
    snap = tracker.calculate(
        session_id="s2", total_cost_usd=0.0,
        tokens_saved=10000, calls=5,
    )
    assert snap.roi_ratio >= 0.0


def test_productivity_score_bounded():
    tracker = ROITracker(dev_hourly_rate_usd=100.0)
    snap = tracker.calculate(
        session_id="s3", total_cost_usd=1.0,
        tokens_saved=100000, calls=50,
    )
    assert 0.0 <= snap.productivity_score <= 1.0


def test_roi_ratio_is_float():
    tracker = ROITracker(dev_hourly_rate_usd=100.0)
    snap = tracker.calculate(
        session_id="s4", total_cost_usd=2.0,
        tokens_saved=5000, calls=10,
    )
    assert isinstance(snap.roi_ratio, float)


def test_time_saved_proportional_to_tokens():
    tracker = ROITracker(dev_hourly_rate_usd=100.0)
    snap1 = tracker.calculate(session_id="s5", total_cost_usd=1.0, tokens_saved=1000, calls=1)
    snap2 = tracker.calculate(session_id="s6", total_cost_usd=1.0, tokens_saved=2000, calls=1)
    assert snap2.estimated_time_saved_min > snap1.estimated_time_saved_min
