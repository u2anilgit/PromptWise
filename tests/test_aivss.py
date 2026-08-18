"""WP2 — AIVSS v0.5 agentic-dimensions threat-scoring rubric (core/aivss.py).
Shared with WP3's incident-response scoring. Pure stdlib, no ML — a
documented weighted rubric, not a black box.
"""
import pytest

from promptwise.core.aivss import AIVSS_FACTORS, AivssScore, score


def test_factors_sum_to_one():
    assert sum(AIVSS_FACTORS.values()) == pytest.approx(1.0)


def test_factors_cover_the_four_agentic_dimensions():
    assert set(AIVSS_FACTORS) == {"autonomy", "tool_access", "memory_persistence", "multi_agent_reach"}


def test_score_all_zero_factors_is_zero():
    result = score({})
    assert result.total == 0.0
    assert isinstance(result, AivssScore)


def test_score_all_max_factors_is_100():
    result = score({k: 100.0 for k in AIVSS_FACTORS})
    assert result.total == pytest.approx(100.0)


def test_score_weights_factors_proportionally():
    # Only autonomy maxed out -- total should equal autonomy's weight * 100.
    result = score({"autonomy": 100.0})
    assert result.total == pytest.approx(AIVSS_FACTORS["autonomy"] * 100.0)


def test_score_breakdown_shows_per_factor_contribution():
    result = score({"autonomy": 50.0, "tool_access": 100.0})
    assert result.breakdown["autonomy"] == pytest.approx(50.0 * AIVSS_FACTORS["autonomy"])
    assert result.breakdown["tool_access"] == pytest.approx(100.0 * AIVSS_FACTORS["tool_access"])
    assert result.breakdown["memory_persistence"] == 0.0


def test_score_clamps_out_of_range_inputs():
    result = score({"autonomy": 150.0, "tool_access": -20.0})
    assert result.breakdown["autonomy"] == pytest.approx(100.0 * AIVSS_FACTORS["autonomy"])
    assert result.breakdown["tool_access"] == 0.0


def test_score_ignores_unknown_factor_keys():
    result = score({"autonomy": 50.0, "not_a_real_factor": 999.0})
    assert result.total == pytest.approx(50.0 * AIVSS_FACTORS["autonomy"])
