"""Tests for QualityGuard."""

from promptwise_v3.core.quality import QualityGuard


def test_quality_empty_string():
    q = QualityGuard(confidence_threshold=0.9)
    r = q.check("")
    assert r.passed is False
    assert "empty_output" in r.signals


def test_quality_ok():
    q = QualityGuard(confidence_threshold=0.6)
    r = q.check("Write a Python function to sort numbers")
    assert r.passed is True
    assert len(r.signals) == 0


def test_quality_refusal():
    q = QualityGuard()
    r = q.check("I cannot help with that request")
    assert "refusal_signal" in r.signals


def test_quality_disabled():
    q = QualityGuard(enabled=False)
    r = q.check("")
    assert r.passed is True
    assert r.score == 1.0
