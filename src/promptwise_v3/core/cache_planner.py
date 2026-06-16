from promptwise_v3.config import AppConfigV3
from promptwise_v3.types import CachePlanResult


class CachePlanner:
    def __init__(self, config: AppConfigV3 | None = None):
        self.config = config or AppConfigV3()

    def plan(self, messages: list[dict], expected_reuse_count: int = 2, model: str = "claude-sonnet-4-6") -> CachePlanResult:
        if not messages:
            return CachePlanResult(breakpoints=[], savings_pct=0.0)

        model_cfg = self.config.get_model(model)
        cache_write_cost = model_cfg.rates.cache_write_per_mtok
        cache_hit_cost = model_cfg.rates.cache_hit_per_mtok
        normal_cost = model_cfg.rates.input_per_mtok

        breakpoints = []
        cumulative_tokens = 0

        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            label = msg.get("label", f"msg_{i}")
            tokens = max(1, len(content) // 4)
            cumulative_tokens += tokens

            if expected_reuse_count > 1 and i < len(messages) - 1:
                placeholder = cumulative_tokens - tokens
                saving_per_call = max(0, (normal_cost - cache_hit_cost) * (placeholder / 1_000_000))
                total_saving = saving_per_call * expected_reuse_count
                write_overhead = cache_write_cost * (placeholder / 1_000_000)

                if total_saving > write_overhead:
                    breakpoints.append({
                        "message_index": i,
                        "ttl": f"{expected_reuse_count}x",
                        "rationale": f"Cache '{label}' — saves ${total_saving - write_overhead:.6f} across {expected_reuse_count} calls",
                    })

        savings_pct = round(min(60.0, len(breakpoints) * 15), 1)
        return CachePlanResult(breakpoints=breakpoints, savings_pct=savings_pct)
