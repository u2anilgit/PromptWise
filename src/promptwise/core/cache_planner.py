from promptwise.config import AppConfig
from promptwise.types import CachePlanResult


class CachePlanner:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()

    # Provider minimum cacheable prefix length (tokens). Anthropic will not create
    # a cache entry below this, so recommending a breakpoint under it is bad advice.
    @staticmethod
    def _min_cacheable_tokens(model: str) -> int:
        return 2048 if "haiku" in (model or "").lower() else 1024

    def plan(self, messages: list[dict], expected_reuse_count: int = 2, model: str = "claude-sonnet-4-6") -> CachePlanResult:
        if not messages:
            return CachePlanResult(breakpoints=[], savings_pct=0.0)

        model_cfg = self.config.get_model(model)
        cache_write_cost = model_cfg.rates.cache_write_per_mtok
        cache_hit_cost = model_cfg.rates.cache_hit_per_mtok
        normal_cost = model_cfg.rates.input_per_mtok
        min_tokens = self._min_cacheable_tokens(model)

        breakpoints = []
        cumulative_tokens = 0
        total_net_saving = 0.0
        total_repeat_cost = 0.0

        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            label = msg.get("label", f"msg_{i}")
            tokens = max(1, len(content) // 4)
            cumulative_tokens += tokens

            if expected_reuse_count > 1 and i < len(messages) - 1:
                # A breakpoint on message i caches the prefix [0..i] INCLUSIVE —
                # that whole span is what the provider stores and re-reads.
                cached_tokens = cumulative_tokens
                # Provider won't cache a prefix shorter than the minimum — skip it.
                if cached_tokens < min_tokens:
                    continue
                saving_per_call = max(0, (normal_cost - cache_hit_cost) * (cached_tokens / 1_000_000))
                total_saving = saving_per_call * expected_reuse_count
                write_overhead = cache_write_cost * (cached_tokens / 1_000_000)
                net = total_saving - write_overhead

                if net > 0:
                    breakpoints.append({
                        "message_index": i,
                        "ttl": f"{expected_reuse_count}x",
                        "cacheable_tokens": cached_tokens,
                        "rationale": f"Cache '{label}' ({cached_tokens} tok prefix) — saves ${net:.6f} across {expected_reuse_count} calls",
                    })
                    total_net_saving += net
                    total_repeat_cost += normal_cost * (cached_tokens / 1_000_000) * expected_reuse_count

        # Real savings: net dollars saved as a fraction of the repeated input cost.
        savings_pct = round(100.0 * total_net_saving / total_repeat_cost, 1) if total_repeat_cost > 0 else 0.0
        return CachePlanResult(breakpoints=breakpoints, savings_pct=savings_pct)
