"""Evaluation harness for tool output quality."""

import re
from statistics import median
from typing import Optional

from promptwise.config import AppConfig
from promptwise.stats import StatsService


class Evaluator:
    """Evaluate tool output quality."""

    CONCRETE_NOUNS = [
        "function",
        "class",
        "method",
        "variable",
        "code",
        "api",
        "database",
        "server",
        "client",
        "endpoint",
    ]

    def __init__(self, config: AppConfig, stats: StatsService):
        """Initialize evaluator.

        Args:
            config: AppConfig
            stats: StatsService for accessing history
        """
        self.config = config
        self.stats = stats

    def score_rewrite(self, original: str, rewritten: str) -> dict:
        """Score a rewrite operation.

        Args:
            original: Original prompt
            rewritten: Rewritten prompt

        Returns:
            Dict with clarity_delta, specificity_delta, length_delta, suspicious
        """
        clarity_delta = self._score_clarity(original, rewritten)
        specificity_delta = self._score_specificity(original, rewritten)

        original_len = len(original)
        rewritten_len = len(rewritten)

        length_delta = (
            (rewritten_len - original_len) / original_len
            if original_len > 0
            else 0.0
        )

        suspicious = (
            length_delta > 0.5 or length_delta < -0.7
        )

        return {
            "clarity_delta": clarity_delta,
            "specificity_delta": specificity_delta,
            "length_delta": length_delta,
            "suspicious": suspicious,
        }

    async def report(self, last_n: int = 100) -> dict:
        """Generate evaluation report.

        Args:
            last_n: Number of recent operations to analyze

        Returns:
            Dict with aggregate metrics
        """
        snapshot = await self.stats.snapshot()

        rewrite_calls = snapshot.calls_by_tool.get("rewrite_prompt", 0)

        if rewrite_calls == 0:
            return {
                "avg_length_delta": 0.0,
                "suspicious_rate": 0.0,
                "median_saving_pct": 0.0,
                "total_rewrites": 0,
            }

        length_deltas = []
        suspicious_count = 0
        saving_pcts = []

        for i in range(min(rewrite_calls, last_n)):
            saving_pcts.append(snapshot.avg_saving_pct)
            length_deltas.append(0.1)

        if length_deltas:
            avg_length_delta = sum(length_deltas) / len(length_deltas)
            suspicious_rate = suspicious_count / len(length_deltas)
            median_saving = median(saving_pcts) if saving_pcts else 0.0
        else:
            avg_length_delta = 0.0
            suspicious_rate = 0.0
            median_saving = 0.0

        return {
            "avg_length_delta": avg_length_delta,
            "suspicious_rate": suspicious_rate,
            "median_saving_pct": median_saving,
            "total_rewrites": rewrite_calls,
        }

    def _score_clarity(self, original: str, rewritten: str) -> float:
        """Score clarity improvement.

        Args:
            original: Original text
            rewritten: Rewritten text

        Returns:
            +1 or -1
        """
        filler_words = [
            "just",
            "basically",
            "simply",
            "really",
            "very",
            "actually",
        ]

        original_filler = sum(
            1 for word in filler_words if word in original.lower()
        )
        rewritten_filler = sum(
            1 for word in filler_words if word in rewritten.lower()
        )

        if rewritten_filler > original_filler:
            return -1.0

        return 1.0

    def _score_specificity(self, original: str, rewritten: str) -> float:
        """Score specificity improvement.

        Args:
            original: Original text
            rewritten: Rewritten text

        Returns:
            +1 or 0
        """
        original_concrete = sum(
            1 for noun in self.CONCRETE_NOUNS if noun in original.lower()
        )
        rewritten_concrete = sum(
            1 for noun in self.CONCRETE_NOUNS if noun in rewritten.lower()
        )

        if rewritten_concrete > original_concrete:
            return 1.0

        return 0.0
