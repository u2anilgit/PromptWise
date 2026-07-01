"""Phase 6 WP5 — responsible-AI advisory heuristics (grounding / bias / ethics).

Every check is advisory: findings are warnings, never hard blocks. Local, stdlib,
no infrastructure.
"""
from promptwise.core import responsible_ai as rai


# ── grounding ────────────────────────────────────────────────────────────────
def test_grounding_not_applicable_without_sources():
    r = rai.check_grounding("The value is 42 and revenue rose sharply.")
    assert r["applicable"] is False


def test_grounding_flags_unsupported_claim():
    r = rai.check_grounding("Revenue grew 250% in the last year.",
                            sources="The report describes weather patterns in the north.")
    assert r["applicable"] is True
    assert any(f["check"] == "grounding" for f in r["findings"])


def test_grounding_supported_claim_scores_higher():
    r = rai.check_grounding("Revenue grew 250 percent this year.",
                            sources="Annual revenue grew 250 percent this year across regions.")
    assert r["score"] >= 0.5


def test_grounding_flags_unbacked_attribution():
    r = rai.check_grounding("Studies show this is the best approach.")
    assert any("attribution" in f["detail"] for f in r["findings"])


# ── bias ─────────────────────────────────────────────────────────────────────
def test_bias_flags_group_generalization():
    r = rai.check_bias("All immigrants are lazy and never contribute.")
    assert any(f["check"] == "bias" for f in r["findings"])


def test_bias_ignores_plain_mention():
    r = rai.check_bias("Immigrants moved to the city looking for new jobs.")
    assert r["findings"] == []


# ── ethics ───────────────────────────────────────────────────────────────────
def test_ethics_flags_advice_without_disclosure():
    r = rai.check_ethics("You should move your retirement fund into this stock right now.")
    assert any(f["check"] == "ethics" for f in r["findings"])


def test_ethics_advice_with_disclaimer_is_clean():
    r = rai.check_ethics("You could invest, but consult a qualified professional first.")
    assert not any("without a disclosure" in f["detail"] for f in r["findings"])


def test_ethics_flags_overconfidence():
    r = rai.check_ethics("This method is completely safe and guaranteed to work.")
    assert any("overconfident" in f["detail"] for f in r["findings"])


# ── aggregate ────────────────────────────────────────────────────────────────
def test_scan_aggregates_and_reports_severity():
    out = rai.scan("All women are bad at math, guaranteed, studies show.")
    assert out["overall"] == "review"
    assert out["highest_severity"] in ("low", "medium", "high")


def test_scan_clean_text_is_clean():
    out = rai.scan("Here is a neutral factual summary of the meeting notes.")
    assert out["overall"] == "clean"
    assert out["findings"] == []


def test_scan_never_raises_on_garbage():
    for bad in ("", "   ", "\n\n", "x" * 5000):
        out = rai.scan(bad)
        assert "overall" in out
