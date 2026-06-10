"""Tests for Optimizer."""

from promptwise_v3.core.optimizer import Optimizer


def test_optimize_empty():
    o = Optimizer()
    r = o.optimize("", token_budget=1000)
    assert r.optimized == ""
    assert r.saving_pct == 0.0


def test_optimize_under_budget():
    o = Optimizer()
    r = o.optimize("short prompt", token_budget=1000)
    assert r.optimized == "short prompt"
    assert r.saving_pct == 0.0


def test_optimize_over_budget():
    o = Optimizer()
    text = "word " * 200
    r = o.optimize(text, token_budget=50)
    assert r.raw_tokens >= 200
    assert r.saving_pct > 0


def test_optimize_chunks_dropped():
    o = Optimizer()
    text = ". ".join(["word"] * 100)
    r = o.optimize(text, token_budget=10)
    assert r.chunks_dropped > 0
