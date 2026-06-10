"""Tests for ROITracker."""

from promptwise_v3.plugins.roi import ROITracker


def test_calculate_zero_cost():
    r = ROITracker()
    s = r.calculate(session_id="s1", total_cost_usd=0.0, tokens_saved=5000)
    assert s.roi_ratio > 0
    assert s.tokens_saved == 5000


def test_calculate_positive_roi():
    r = ROITracker()
    s = r.calculate(session_id="s1", total_cost_usd=1.0, tokens_saved=6000)
    assert s.roi_ratio > 1.0
    assert s.productivity_score <= 1.0


def test_calculate_low_roi():
    r = ROITracker()
    s = r.calculate(session_id="s1", total_cost_usd=100.0, tokens_saved=100)
    assert s.roi_ratio < 1.0


def test_calculate_with_dev_role():
    r = ROITracker()
    s = r.calculate(session_id="s1", total_cost_usd=5.0, tokens_saved=15000,
                    developer="Alice", role="Dev")
    assert s.roi_ratio > 0
