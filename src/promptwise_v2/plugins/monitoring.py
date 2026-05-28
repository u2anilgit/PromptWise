from promptwise_v2.types_v2 import PluginEvent

_ENERGY_SCORES: dict[str, float] = {
    "claude-haiku-4-5-20251001": 1.0,
    "claude-sonnet-4-6": 0.6,
    "claude-opus-4-7": 0.2,
}
_DEFAULT_ENERGY = 0.4


class CostMonitor:
    def __init__(self, alert_threshold_usd_per_min: float = 5.0):
        self._threshold = alert_threshold_usd_per_min

    def record_step(self, cost_usd: float, duration_ms: int) -> PluginEvent | None:
        rate = self.burn_rate_usd_per_min(cost_usd, duration_ms)
        if rate > self._threshold:
            return PluginEvent(
                plugin_name="monitoring",
                trigger=f"cost overspend: {rate:.2f} USD/min > {self._threshold} threshold",
                action_taken="alert_raised",
                metadata={"rate_usd_per_min": rate, "cost_usd": cost_usd},
            )
        return None

    def burn_rate_usd_per_min(self, cost_usd: float, duration_ms: int) -> float:
        minutes = max(duration_ms / 60000, 0.001)
        return round(cost_usd / minutes, 6)

    def energy_efficiency_score(self, model: str, tokens: int) -> float:
        return _ENERGY_SCORES.get(model, _DEFAULT_ENERGY)
