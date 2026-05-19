"""Context optimization by chunking and scoring."""

import re
from collections import Counter

from promptwise.config import AppConfig
from promptwise.tokenizer import count_tokens
from promptwise.types import OptimizeResult


class Optimizer:
    """Optimize context to fit token budget."""

    def __init__(self, config: AppConfig):
        """Initialize optimizer with config.

        Args:
            config: AppConfig
        """
        self.config = config

    def optimize(
        self,
        context: str,
        token_budget: int = 2000,
        model: str = "claude-sonnet-4-6",
    ) -> OptimizeResult:
        """Optimize context to fit token budget.

        Args:
            context: Context text to optimize
            token_budget: Max tokens allowed
            model: Model for token counting

        Returns:
            OptimizeResult with optimized text and stats
        """
        if not context.strip():
            return OptimizeResult(
                original=context,
                optimized=context,
                raw_tokens=0,
                optimized_tokens=0,
                saving_pct=0.0,
                chunks_dropped=0,
                budget=token_budget,
                cache_candidates=[],
                model_used_for_count=model,
            )

        raw_count = count_tokens(context, model)

        if raw_count.value <= token_budget:
            return OptimizeResult(
                original=context,
                optimized=context,
                raw_tokens=raw_count.value,
                optimized_tokens=raw_count.value,
                saving_pct=0.0,
                chunks_dropped=0,
                budget=token_budget,
                cache_candidates=[],
                model_used_for_count=model,
            )

        chunks = self._split_chunks(context)

        for i, chunk in enumerate(chunks):
            chunk["tokens"] = count_tokens(chunk["text"], model).value
            chunk["index"] = i

        chunks_with_scores = [
            {**chunk, "score": self._score_chunk(chunk, len(chunks))}
            for chunk in chunks
        ]

        kept_chunks = []
        current_tokens = 0

        # Code blocks are always kept (never droppable)
        for chunk in chunks_with_scores:
            if not self._can_drop(chunk):
                kept_chunks.append(chunk)
                current_tokens += chunk["tokens"]

        # Fill remaining budget with highest-scored droppable chunks
        droppable = sorted(
            [c for c in chunks_with_scores if self._can_drop(c)],
            key=lambda x: x["score"],
            reverse=True,
        )
        for chunk in droppable:
            if current_tokens + chunk["tokens"] <= token_budget:
                kept_chunks.append(chunk)
                current_tokens += chunk["tokens"]

        kept_chunks_sorted = sorted(kept_chunks, key=lambda x: x["index"])
        optimized_text = "\n".join([c["text"] for c in kept_chunks_sorted])

        optimized_count = count_tokens(optimized_text, model)
        chunks_dropped = len(chunks) - len(kept_chunks)

        saving_pct = (
            (raw_count.value - optimized_count.value) / raw_count.value * 100
            if raw_count.value > 0
            else 0.0
        )

        cache_candidates = [
            c["text"]
            for c in kept_chunks_sorted
            if c["tokens"] > 1000
        ]

        return OptimizeResult(
            original=context,
            optimized=optimized_text,
            raw_tokens=raw_count.value,
            optimized_tokens=optimized_count.value,
            saving_pct=saving_pct,
            chunks_dropped=chunks_dropped,
            budget=token_budget,
            cache_candidates=cache_candidates,
            model_used_for_count=model,
        )

    def _split_chunks(self, text: str) -> list[dict]:
        """Split text into chunks respecting code blocks.

        Args:
            text: Text to split

        Returns:
            List of chunks with text and metadata
        """
        chunks = []
        in_code_block = False
        current_chunk = []

        for line in text.split("\n"):
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                current_chunk.append(line)
            elif in_code_block:
                current_chunk.append(line)
            elif line.strip() == "":
                if current_chunk:
                    chunk_text = "\n".join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(
                            {
                                "text": chunk_text,
                                "has_code_block": "```" in chunk_text,
                                "has_header": self._is_header(
                                    current_chunk[0] if current_chunk else ""
                                ),
                            }
                        )
                    current_chunk = []
            elif self._is_header(line):
                if current_chunk and current_chunk[-1].strip() != "":
                    chunk_text = "\n".join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(
                            {
                                "text": chunk_text,
                                "has_code_block": "```" in chunk_text,
                                "has_header": False,
                            }
                        )
                    current_chunk = [line]
                else:
                    current_chunk.append(line)
            else:
                current_chunk.append(line)

        if current_chunk:
            chunk_text = "\n".join(current_chunk).strip()
            if chunk_text:
                chunks.append(
                    {
                        "text": chunk_text,
                        "has_code_block": "```" in chunk_text,
                        "has_header": self._is_header(current_chunk[0] if current_chunk else ""),
                    }
                )

        return chunks if chunks else [{"text": text, "has_code_block": False, "has_header": False}]

    def _is_header(self, line: str) -> bool:
        """Check if line is markdown header.

        Args:
            line: Line to check

        Returns:
            True if line is header
        """
        return bool(re.match(r"^#{1,6}\s", line))

    def _score_chunk(self, chunk: dict, total_chunks: int) -> float:
        """Score chunk by position, keyword density, and header.

        Args:
            chunk: Chunk with index and text
            total_chunks: Total number of chunks

        Returns:
            Score between 0 and 1
        """
        index = chunk["index"]

        if total_chunks == 1:
            position_score = 1.0
        else:
            is_first_or_last = index == 0 or index == total_chunks - 1
            if is_first_or_last:
                position_score = 1.0
            else:
                middle_distance = 1.0 - (
                    abs(index - (total_chunks - 1) / 2) / ((total_chunks - 1) / 2)
                )
                position_score = max(0.0, middle_distance)

        words = chunk["text"].lower().split()
        unique_words = len(set(words))
        total_words = len(words)
        keyword_density = (
            min(unique_words / total_words, 1.0) if total_words > 0 else 0.0
        )

        has_header = 1.0 if chunk["has_header"] else 0.0

        score = (
            0.5 * position_score + 0.3 * keyword_density + 0.2 * has_header
        )

        return score

    def _can_drop(self, chunk: dict) -> bool:
        """Check if chunk can be dropped.

        Args:
            chunk: Chunk to check

        Returns:
            False if chunk has code block (cannot drop)
        """
        return not chunk.get("has_code_block", False)
