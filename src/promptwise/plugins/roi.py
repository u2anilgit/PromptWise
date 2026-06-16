from promptwise.types import ROISnapshot

_TOKENS_PER_MIN = 300


class ROITracker:
    def __init__(self, dev_hourly_rate_usd: float = 100.0):
        self._hourly_rate = dev_hourly_rate_usd

    def calculate(self, *, session_id: str, total_cost_usd: float, tokens_saved: int, calls: int = 1,
                  developer: str = "Anonymous", role: str = "Dev") -> ROISnapshot:
        time_saved_min = tokens_saved / _TOKENS_PER_MIN
        value_usd = (time_saved_min / 60) * self._hourly_rate
        roi = round(value_usd / total_cost_usd, 3) if total_cost_usd > 0 else round(value_usd, 3)
        productivity = round(min(1.0, roi / 10.0), 3)
        return ROISnapshot(session_id=session_id, total_cost_usd=round(total_cost_usd, 6), tokens_saved=tokens_saved,
                           estimated_time_saved_min=round(time_saved_min, 2), roi_ratio=roi, productivity_score=productivity)
