"""Tests for Summarizer."""

from promptwise_v3.core.summarizer import Summarizer


def test_summarize_conversation():
    s = Summarizer()
    result = s.summarize("Hello. How can I help?")
    assert result.summary is not None
    assert len(result.summary) > 0


def test_summarize_empty():
    s = Summarizer()
    result = s.summarize("")
    assert result.summary == ""
    assert result.original_tokens == 0


def test_summarize_reset_prompt():
    s = Summarizer()
    result = s.summarize("Hello. Hi. How are you?")
    assert result.reset_prompt is not None
    assert len(result.reset_prompt) > 0


def test_summarize_saving_pct():
    s = Summarizer()
    result = s.summarize("A. B. C. D. E. F. G. H. I. J.")
    assert result.saving_pct > 0
