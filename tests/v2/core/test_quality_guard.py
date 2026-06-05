"""Tests for QualityGuard — confidence scoring and hallucination signal detection."""
import pytest
from promptwise_v2.core.quality_guard import QualityGuard, QualityResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_guard(threshold: float = 0.6, enabled: bool = True) -> QualityGuard:
    return QualityGuard(confidence_threshold=threshold, enabled=enabled)


# ---------------------------------------------------------------------------
# Test 1 — disabled guard always passes with perfect score
# ---------------------------------------------------------------------------

def test_disabled_guard_returns_perfect_score():
    guard = make_guard(enabled=False)
    result = guard.check("some output", skill_name="anything")
    assert result.score == 1.0
    assert result.passed is True
    assert result.signals == []


def test_disabled_guard_empty_output_still_passes():
    guard = make_guard(enabled=False)
    result = guard.check("")
    assert result.passed is True
    assert result.score == 1.0


# ---------------------------------------------------------------------------
# Test 2 — clean output
# ---------------------------------------------------------------------------

def test_clean_string_passes_default_threshold():
    guard = make_guard()
    result = guard.check("The function calculates the sum of all elements in a list.")
    assert result.passed is True
    assert result.signals == []
    assert result.score == pytest.approx(1.0)


def test_clean_dict_passes():
    guard = make_guard()
    result = guard.check({"status": "ok", "data": [1, 2, 3]})
    assert result.passed is True
    assert result.signals == []


# ---------------------------------------------------------------------------
# Test 3 — empty output
# ---------------------------------------------------------------------------

def test_empty_string_raises_empty_output_signal():
    guard = make_guard()
    result = guard.check("")
    assert "empty_output" in result.signals
    assert result.score < 1.0


def test_whitespace_only_raises_empty_output_signal():
    guard = make_guard()
    result = guard.check("   \n\t  ")
    assert "empty_output" in result.signals


def test_empty_output_score_reduced_by_0_15():
    guard = make_guard()
    result = guard.check("")
    # 1 signal → score = 1.0 - 0.15 = 0.85
    assert result.score == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Test 4 — incomplete / placeholder markers
# ---------------------------------------------------------------------------

def test_todo_in_output_raises_incomplete_signal():
    guard = make_guard()
    result = guard.check("Here is the plan: TODO implement the main logic later.")
    assert "incomplete_output" in result.signals


def test_fixme_in_output_raises_incomplete_signal():
    guard = make_guard()
    result = guard.check("FIXME: this section is not finished yet.")
    assert "incomplete_output" in result.signals


def test_placeholder_brackets_raises_incomplete_signal():
    guard = make_guard()
    result = guard.check("Replace [placeholder] with actual content.")
    assert "incomplete_output" in result.signals


def test_ellipsis_raises_incomplete_signal():
    guard = make_guard()
    result = guard.check("The answer is somewhere in the docs...")
    assert "incomplete_output" in result.signals


# ---------------------------------------------------------------------------
# Test 5 — refusal signal
# ---------------------------------------------------------------------------

def test_i_cannot_raises_refusal_signal():
    guard = make_guard()
    result = guard.check("I cannot help with that request as it violates policy.")
    assert "refusal_signal" in result.signals


def test_i_dont_know_raises_refusal_signal():
    guard = make_guard()
    result = guard.check("I don't know the answer to your question.")
    assert "refusal_signal" in result.signals


def test_im_not_sure_raises_refusal_signal():
    guard = make_guard()
    result = guard.check("I'm not sure about the exact details here.")
    assert "refusal_signal" in result.signals


# ---------------------------------------------------------------------------
# Test 6 — contradictory output
# ---------------------------------------------------------------------------

def test_success_and_failed_raises_contradictory_signal():
    guard = make_guard()
    result = guard.check("The operation was a success but later failed unexpectedly.")
    assert "contradictory_output" in result.signals


def test_contradictory_case_insensitive():
    guard = make_guard()
    result = guard.check("SUCCESS was logged, then FAILED error thrown.")
    assert "contradictory_output" in result.signals


def test_only_success_no_contradictory_signal():
    guard = make_guard()
    result = guard.check("The operation was a success.")
    assert "contradictory_output" not in result.signals


def test_only_failed_no_contradictory_signal():
    guard = make_guard()
    result = guard.check("The task failed with exit code 1.")
    assert "contradictory_output" not in result.signals


# ---------------------------------------------------------------------------
# Test 7 — low threshold → still passes even with signals
# ---------------------------------------------------------------------------

def test_low_threshold_passes_with_one_signal():
    guard = make_guard(threshold=0.1)
    # TODO → incomplete_output signal → score = 0.85, threshold = 0.1
    result = guard.check("TODO: implement this", skill_name="anything")
    assert "incomplete_output" in result.signals
    assert result.passed is True


def test_low_threshold_passes_with_two_signals():
    # Empty + incomplete → score = 1.0 - 0.15*2 = 0.70, threshold = 0.1 → pass
    guard = make_guard(threshold=0.1)
    # Empty string also triggers "empty_output"; add TODO for incomplete_output
    # But empty string won't contain TODO, so craft a non-empty string with 2 signals.
    result = guard.check("TODO fix this ... more ellipsis", skill_name="")
    # "TODO" → incomplete_output; "..." → also incomplete_output, but it's the same signal (deduped via list)
    # Actually both markers count as the SAME signal — only one signal fires.
    # Let's use refusal + incomplete for 2 distinct signals.
    result2 = guard.check("I cannot help. TODO: fix this later.", skill_name="")
    assert result2.passed is True
    assert result2.score == pytest.approx(1.0 - 0.15 * len(result2.signals))


# ---------------------------------------------------------------------------
# Test 8 — high threshold → fails with 2 signals
# ---------------------------------------------------------------------------

def test_high_threshold_fails_with_two_signals():
    # Signals: refusal_signal + incomplete_output → score = 1.0 - 0.30 = 0.70
    # threshold = 0.9 → passed = False
    guard = make_guard(threshold=0.9)
    result = guard.check("I cannot help. TODO: this is not done.")
    assert "refusal_signal" in result.signals
    assert "incomplete_output" in result.signals
    assert len(result.signals) >= 2
    assert result.score == pytest.approx(1.0 - 0.15 * len(result.signals))
    assert result.passed is False


def test_high_threshold_fails_with_contradictory_and_refusal():
    guard = make_guard(threshold=0.9)
    result = guard.check("Success was achieved but then it failed. I'm not sure why.")
    assert "contradictory_output" in result.signals
    assert "refusal_signal" in result.signals
    assert result.passed is False


# ---------------------------------------------------------------------------
# Test 9 — score boundary / clamp
# ---------------------------------------------------------------------------

def test_score_never_below_zero():
    guard = make_guard(threshold=0.0)
    # Craft output hitting many signals: empty + refusal (empty string won't have refusal text)
    # Use a string with refusal + incomplete + contradictory = 3 signals → 1.0 - 0.45 = 0.55
    # For 7 signals: score would be negative without clamping; use many markers
    text = "I cannot. I don't know. TODO. FIXME. [placeholder]. ... success failed."
    result = guard.check(text)
    assert result.score >= 0.0


def test_result_is_quality_result_instance():
    guard = make_guard()
    result = guard.check("Hello world")
    assert isinstance(result, QualityResult)


# ---------------------------------------------------------------------------
# Test 10 — QualityResult fields
# ---------------------------------------------------------------------------

def test_quality_result_fields_present():
    result = QualityResult(score=0.85, passed=True, signals=["incomplete_output"])
    assert result.score == 0.85
    assert result.passed is True
    assert result.signals == ["incomplete_output"]
