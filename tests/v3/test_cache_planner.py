"""Tests for CachePlanner."""

from promptwise_v3.core.cache_planner import CachePlanner


def test_plan_empty():
    cp = CachePlanner()
    result = cp.plan([])
    assert len(result.breakpoints) == 0
    assert result.savings_pct == 0.0


def test_plan_single_message():
    cp = CachePlanner()
    result = cp.plan([{"content": "Hello", "label": "msg_0"}])
    assert len(result.breakpoints) == 0


def test_plan_multiple_messages():
    cp = CachePlanner()
    msgs = [{"content": f"prompt {i}", "label": f"msg_{i}"} for i in range(5)]
    result = cp.plan(msgs, expected_reuse_count=3)
    assert result.savings_pct >= 0


def test_plan_no_reuse():
    cp = CachePlanner()
    msgs = [{"content": "hello"}] * 3
    result = cp.plan(msgs, expected_reuse_count=1)
    assert len(result.breakpoints) == 0
