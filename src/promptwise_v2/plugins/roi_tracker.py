import asyncio
from promptwise_v2.types_v2 import ROISnapshot

_TOKENS_PER_MINUTE_TYPING = 300


class ROITracker:
    def __init__(self, dev_hourly_rate_usd: float = 100.0):
        self._hourly_rate = dev_hourly_rate_usd

    def calculate(self, *, session_id: str, total_cost_usd: float,
                  tokens_saved: int, calls: int, memory_manager=None,
                  developer: str = "Anonymous", role: str = "Dev") -> ROISnapshot:
        time_saved_min = tokens_saved / _TOKENS_PER_MINUTE_TYPING
        value_of_time_usd = (time_saved_min / 60) * self._hourly_rate

        if total_cost_usd > 0:
            roi_ratio = round(value_of_time_usd / total_cost_usd, 3)
        else:
            roi_ratio = round(value_of_time_usd, 3)

        # Cap productivity score at 1.0
        productivity_score = round(min(1.0, roi_ratio / 10.0), 3)

        if memory_manager:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(
                        memory_manager.log_roi_stat(
                            developer, role, float(tokens_saved), float(total_cost_usd), time_saved_min / 60.0
                        )
                    )
            except Exception:
                pass

        return ROISnapshot(
            session_id=session_id,
            total_cost_usd=round(total_cost_usd, 6),
            tokens_saved=tokens_saved,
            estimated_time_saved_min=round(time_saved_min, 2),
            roi_ratio=roi_ratio,
            productivity_score=productivity_score,
        )
