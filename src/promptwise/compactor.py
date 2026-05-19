"""Auto-compact conversation turns when token thresholds are exceeded."""

from promptwise.config import AppConfig
from promptwise.summarizer import Summarizer
from promptwise.tokenizer import count_tokens
from promptwise.types import CompactResult

_DECISION_KEYWORDS = Summarizer.DECISION_KEYWORDS


class Compactor:
    """Score and drop low-value turns to fit within token budget."""

    def __init__(self, config: AppConfig):
        self.config = config

    def compact(
        self,
        turns: list[dict],
        model: str = "claude-sonnet-4-6",
        threshold_pct: float | None = None,
        threshold_tokens: int | None = None,
        target_tokens: int | None = None,
    ) -> CompactResult:
        """Compact turns if either threshold is exceeded.

        Args:
            turns: List of {role, content} dicts in chronological order
            model: Model for token counting and context window lookup
            threshold_pct: Override config threshold_pct (fraction of context window)
            threshold_tokens: Override config threshold_tokens (absolute count)
            target_tokens: Override target budget (default: context_window * target_pct)

        Returns:
            CompactResult with status "ok" (no action) or "compacted"
        """
        if not turns:
            return CompactResult(
                status="ok",
                original_tokens=0,
                compacted_tokens=0,
                turns_kept=0,
                turns_dropped=0,
                saving_pct=0.0,
                compacted_turns=[],
                threshold_used="none",
                model_used_for_count=model,
            )

        eff_threshold_pct = threshold_pct if threshold_pct is not None else self.config.auto_compact.threshold_pct
        eff_threshold_tokens = threshold_tokens if threshold_tokens is not None else self.config.auto_compact.threshold_tokens
        target_pct = self.config.auto_compact.target_pct

        context_window = self._context_window(model)
        pct_threshold_tokens = int(context_window * eff_threshold_pct)
        eff_target_tokens = target_tokens if target_tokens is not None else int(context_window * target_pct)

        total_tokens = sum(count_tokens(t["content"], model).value for t in turns)

        threshold_used = "none"
        if total_tokens > eff_threshold_tokens:
            threshold_used = "tokens"
        elif total_tokens > pct_threshold_tokens:
            threshold_used = "pct"

        if threshold_used == "none":
            return CompactResult(
                status="ok",
                original_tokens=total_tokens,
                compacted_tokens=total_tokens,
                turns_kept=len(turns),
                turns_dropped=0,
                saving_pct=0.0,
                compacted_turns=list(turns),
                threshold_used="none",
                model_used_for_count=model,
            )

        # Score each turn, keeping track of original index for chronological restore
        scored = [
            (i, turn, self._score_turn(turn, i, len(turns)))
            for i, turn in enumerate(turns)
        ]

        # Pinned turns (system role) always kept
        pinned = [(i, t, s) for i, t, s in scored if t["role"] == "system"]
        droppable = sorted(
            [(i, t, s) for i, t, s in scored if t["role"] != "system"],
            key=lambda x: x[2],
        )

        kept = list(pinned)
        current_tokens = sum(count_tokens(t["content"], model).value for _, t, _ in pinned)

        for i, turn, score in reversed(droppable):
            turn_tokens = count_tokens(turn["content"], model).value
            if current_tokens + turn_tokens <= eff_target_tokens:
                kept.append((i, turn, score))
                current_tokens += turn_tokens

        kept.sort(key=lambda x: x[0])
        compacted_turns = [t for _, t, _ in kept]

        compacted_tokens = sum(count_tokens(t["content"], model).value for t in compacted_turns)
        saving_pct = (
            (total_tokens - compacted_tokens) / total_tokens * 100
            if total_tokens > 0 else 0.0
        )

        return CompactResult(
            status="compacted",
            original_tokens=total_tokens,
            compacted_tokens=compacted_tokens,
            turns_kept=len(compacted_turns),
            turns_dropped=len(turns) - len(compacted_turns),
            saving_pct=saving_pct,
            compacted_turns=compacted_turns,
            threshold_used=threshold_used,
            model_used_for_count=model,
        )

    def _context_window(self, model: str) -> int:
        model_info = self.config.pricing.models.get(model)
        if model_info:
            return model_info.context_window
        return 200000  # safe fallback for unknown models

    def _score_turn(self, turn: dict, index: int, total: int) -> float:
        score = 0.0
        content = turn.get("content", "")
        content_lower = content.lower()

        if "```" in content:
            score += 2.0

        if any(kw in content_lower for kw in _DECISION_KEYWORDS):
            score += 2.0

        if total > 0:
            last_20_pct_start = max(0, int(total * 0.8))
            if index >= last_20_pct_start:
                score += 1.5

        if index == 0:
            score += 0.5

        if turn.get("role") == "assistant":
            score += 0.3

        return score
