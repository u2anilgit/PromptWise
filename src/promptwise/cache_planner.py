"""Cache planning for prompt prefix reuse."""

from promptwise.config import AppConfig
from promptwise.tokenizer import count_tokens
from promptwise.types import CacheBreakpoint, CachePlanResult


class CachePlanner:
    """Plan cache breakpoints for repeated calls."""

    def __init__(self, config: AppConfig):
        """Initialize cache planner with config.

        Args:
            config: AppConfig with pricing
        """
        self.config = config

    def plan(
        self,
        messages: list[dict],
        expected_reuse_count: int = 2,
        model: str = "claude-sonnet-4-6",
    ) -> CachePlanResult:
        """Plan cache breakpoints for messages.

        Args:
            messages: List of message dicts with role, content, optional label
            expected_reuse_count: How many times these messages will be reused
            model: Model for token counting

        Returns:
            CachePlanResult with breakpoints and savings
        """
        breakpoints = []
        notes = []
        total_cached_tokens = 0

        for i, msg in enumerate(messages):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            label = msg.get("label")

            token_count = count_tokens(content, model).value

            cache_ttl = None
            rationale = None

            if role == "system":
                cache_ttl = "1h"
                rationale = "system prompt (stable across calls)"
            elif role == "user" and label == "tool_definitions":
                cache_ttl = "1h"
                rationale = "tool definitions (stable across calls)"
            elif (
                role == "user"
                and label == "reference"
                and token_count >= 1000
            ):
                cache_ttl = "1h"
                rationale = f"large reference ({token_count} tokens, break-even at 2 reuses)"
            elif (
                role == "user"
                and label == "conversation_history"
                and token_count > 2000
            ):
                cache_ttl = "5m"
                rationale = f"conversation history prefix ({token_count} tokens)"

            if cache_ttl:
                breakpoints.append(
                    CacheBreakpoint(
                        message_index=i,
                        ttl=cache_ttl,
                        rationale=rationale,
                        tokens=token_count,
                    )
                )
                notes.append(f"{rationale} cached at {cache_ttl}")
                total_cached_tokens += token_count

        cost_without_cache = self._calc_cost_without_cache(
            messages, expected_reuse_count, model
        )
        cost_with_cache = self._calc_cost_with_cache(
            messages, breakpoints, expected_reuse_count, model
        )

        savings_pct = (
            (cost_without_cache - cost_with_cache) / cost_without_cache * 100
            if cost_without_cache > 0
            else 0.0
        )

        return CachePlanResult(
            breakpoints=breakpoints,
            cost_without_cache_usd=cost_without_cache,
            cost_with_cache_usd=cost_with_cache,
            savings_pct=savings_pct,
            notes=notes,
            expected_reuse_count=expected_reuse_count,
        )

    def _calc_cost_without_cache(
        self, messages: list[dict], reuse_count: int, model: str
    ) -> float:
        """Calculate cost without caching."""
        model_config = self.config.pricing.models[model]
        input_rate = model_config.rates.input_per_mtok / 1_000_000

        total_tokens = sum(
            count_tokens(m.get("content", ""), model).value for m in messages
        )

        return round(total_tokens * input_rate * reuse_count, 6)

    def _calc_cost_with_cache(
        self, messages: list[dict], breakpoints: list[CacheBreakpoint],
        reuse_count: int, model: str
    ) -> float:
        """Calculate cost with caching."""
        model_config = self.config.pricing.models[model]
        input_rate = model_config.rates.input_per_mtok / 1_000_000
        cache_write_rate = model_config.rates.cache_write_5m_per_mtok / 1_000_000
        cache_hit_rate = model_config.rates.cache_hit_per_mtok / 1_000_000

        if not breakpoints:
            total_tokens = sum(
                count_tokens(m.get("content", ""), model).value
                for m in messages
            )
            return round(total_tokens * input_rate * reuse_count, 6)

        cached_tokens = sum(bp.tokens for bp in breakpoints)
        uncached_tokens = sum(
            count_tokens(m.get("content", ""), model).value
            for m in messages
        ) - cached_tokens

        cache_cost = (
            cached_tokens * cache_write_rate
            + cached_tokens * cache_hit_rate * (reuse_count - 1)
        )
        standard_cost = uncached_tokens * input_rate * reuse_count

        return round(cache_cost + standard_cost, 6)
