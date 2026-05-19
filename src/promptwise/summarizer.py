"""Compress conversations for handoff."""

import re

from promptwise.config import AppConfig
from promptwise.tokenizer import count_tokens
from promptwise.types import SummaryResult


class Summarizer:
    """Summarize conversations for fresh thread context."""

    DECISION_KEYWORDS = [
        "decided",
        "conclusion",
        "final",
        "output",
        "result",
        "solution",
        "agreed",
        "confirmed",
    ]

    def __init__(self, config: AppConfig):
        """Initialize summarizer with config.

        Args:
            config: AppConfig
        """
        self.config = config

    def summarize(
        self,
        conversation: str,
        max_tokens: int = 500,
        model: str = "claude-sonnet-4-6",
    ) -> SummaryResult:
        """Summarize conversation for fresh thread.

        Args:
            conversation: Full conversation text
            max_tokens: Max tokens for summary
            model: Model for token counting

        Returns:
            SummaryResult with summary and stats
        """
        if not conversation.strip():
            return SummaryResult(
                summary="",
                reset_prompt="Context for fresh thread:\n\n\n\n[Summarized from 0 tokens]",
                original_tokens=0,
                summary_tokens=0,
                saving_pct=0.0,
                sentences_kept=0,
                sentences_dropped=0,
                model_used_for_count=model,
            )

        original_tokens = count_tokens(conversation, model).value

        sentences = self._split_sentences(conversation)

        if not sentences:
            return SummaryResult(
                summary="",
                reset_prompt="Context for fresh thread:\n\n\n\n[Summarized from 0 tokens]",
                original_tokens=original_tokens,
                summary_tokens=0,
                saving_pct=0.0,
                sentences_kept=0,
                sentences_dropped=len(sentences),
                model_used_for_count=model,
            )

        scored_sentences = [
            (i, sent, self._score_sentence(sent, i, len(sentences)))
            for i, sent in enumerate(sentences)
        ]

        sorted_by_score = sorted(
            scored_sentences, key=lambda x: x[2], reverse=True
        )

        kept_sentences = []
        current_tokens = 0

        for idx, sent, score in sorted_by_score:
            sent_tokens = count_tokens(sent, model).value
            if current_tokens + sent_tokens <= max_tokens:
                kept_sentences.append((idx, sent))
                current_tokens += sent_tokens

        forced_last_3 = [
            (i, s)
            for i, s in enumerate(sentences[-3:], len(sentences) - 3)
            if current_tokens + count_tokens(s, model).value <= max_tokens
        ]

        for idx, sent in forced_last_3:
            if not any(i == idx for i, _ in kept_sentences):
                kept_sentences.append((idx, sent))

        kept_sentences.sort(key=lambda x: x[0])
        summary_text = " ".join(s for _, s in kept_sentences)

        summary_tokens = count_tokens(summary_text, model).value

        saving_pct = (
            (original_tokens - summary_tokens) / original_tokens * 100
            if original_tokens > 0
            else 0.0
        )

        reset_prompt = (
            f"Context for fresh thread:\n\n{summary_text}\n\n"
            f"[Summarized from {original_tokens} tokens]"
        )

        return SummaryResult(
            summary=summary_text,
            reset_prompt=reset_prompt,
            original_tokens=original_tokens,
            summary_tokens=summary_tokens,
            saving_pct=saving_pct,
            sentences_kept=len(kept_sentences),
            sentences_dropped=len(sentences) - len(kept_sentences),
            model_used_for_count=model,
        )

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        pattern = r"(?<=[.!?])\s+(?=[A-Z])"
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def _score_sentence(self, sentence: str, index: int, total: int) -> float:
        """Score sentence for importance.

        Args:
            sentence: Sentence to score
            index: Position in conversation (0-based)
            total: Total sentences

        Returns:
            Score (higher = more important)
        """
        score = 0.0

        sentence_lower = sentence.lower()
        if any(kw in sentence_lower for kw in self.DECISION_KEYWORDS):
            score += 2.0

        if total > 0:
            last_20_pct_start = max(0, int(total * 0.8))
            if index >= last_20_pct_start:
                score += 1.0

        if index == 0:
            score += 0.5

        return score
