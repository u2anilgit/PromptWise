from promptwise_v2.types_v2 import BudgetStatus


class BudgetGuardian:
    def __init__(self, limit_usd: float = 10.0, team_budget_usd: float = 100.0):
        self.limit_usd = limit_usd
        self.team_budget_usd = team_budget_usd

    def check(self, used_usd: float, days_elapsed: int, project_id: str | None = None) -> BudgetStatus:
        pct_used = round(used_usd / self.limit_usd * 100, 1)
        daily_burn = round(used_usd / max(days_elapsed, 1), 4)
        projected_monthly = round(daily_burn * 30, 4)

        if used_usd >= self.limit_usd:
            alert_level = "hard_stop"
        elif pct_used >= 90:
            alert_level = "critical"
        elif pct_used >= 70:
            alert_level = "warn"
        else:
            alert_level = "ok"

        return BudgetStatus(
            used_usd=round(used_usd, 4),
            limit_usd=self.limit_usd,
            pct_used=pct_used,
            daily_burn_usd=daily_burn,
            projected_monthly_usd=projected_monthly,
            alert_level=alert_level,
            project_id=project_id,
        )

    def predict_cost(self, prompt: str, model: str = "claude-sonnet-4-6") -> dict:
        """Estimate cost before sending. token_count = len(prompt)/4 (rough).
        Pricing per 1M tokens: haiku input=0.8/output=4, sonnet input=3/output=15, opus input=15/output=75.
        Assume output = input * 2.
        Return {estimated_input_tokens, estimated_output_tokens, estimated_cost_usd, model, recommendation}
        recommendation: "haiku" if cost > limit*0.1, else use requested model.
        """
        _pricing = {
            "haiku":  {"input": 0.8,  "output": 4.0},
            "sonnet": {"input": 3.0,  "output": 15.0},
            "opus":   {"input": 15.0, "output": 75.0},
        }
        # Resolve model tier key
        model_lower = model.lower()
        if "haiku" in model_lower:
            tier = "haiku"
        elif "opus" in model_lower:
            tier = "opus"
        else:
            tier = "sonnet"

        pricing = _pricing[tier]
        input_tokens = max(1, len(prompt) // 4)
        output_tokens = input_tokens * 2
        cost_usd = (
            input_tokens * pricing["input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
        )

        # Recommend cheaper model if cost exceeds 10% of limit
        if cost_usd > self.limit_usd * 0.1:
            recommendation = "haiku"
        else:
            recommendation = tier

        return {
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_cost_usd": round(cost_usd, 8),
            "model": model,
            "recommendation": recommendation,
        }

    def set_limit(self, limit_usd: float, period: str = "monthly") -> None:
        """Store limit in self._limits dict: {period: limit_usd}. Persist to config if possible."""
        if not hasattr(self, "_limits"):
            self._limits = {}
        self._limits[period] = limit_usd
        # Also update the primary limit if period is monthly (backward-compat)
        if period == "monthly":
            self.limit_usd = limit_usd

    def get_budget_status(self) -> dict:
        """Return {limit_usd, period, current_spend_usd, pct_used, days_remaining_at_burn_rate}.
        current_spend_usd comes from memory if available, else 0. days_remaining = (limit - spent) / daily_burn if daily_burn > 0."""
        if not hasattr(self, "_limits"):
            self._limits = {}
        period = "monthly"
        limit = self._limits.get(period, self.limit_usd)

        # current_spend is tracked in _spend if available (set by monitor_budget calls), else 0
        current_spend = getattr(self, "_current_spend", 0.0)
        pct_used = round(current_spend / limit * 100, 2) if limit > 0 else 0.0

        # Estimate daily burn from tracked spend; fall back to 0
        daily_burn = getattr(self, "_daily_burn", 0.0)
        if daily_burn > 0:
            days_remaining = round((limit - current_spend) / daily_burn, 1)
        else:
            days_remaining = None

        return {
            "limit_usd": limit,
            "period": period,
            "current_spend_usd": round(current_spend, 6),
            "pct_used": pct_used,
            "days_remaining_at_burn_rate": days_remaining,
        }

    def cost_anomaly_detect(self, daily_costs: list[float]) -> dict:
        """
        Returns alert if latest cost > 2x 7-day rolling average.

        - daily_costs: list of recent daily costs (oldest first, latest last)
        - Uses last 7 entries as the rolling window (or all if fewer than 7)
        - Compares daily_costs[-1] against 2x mean of the window
        - Returns {"alert": bool, "reason": str, "latest": float, "avg_7d": float}
        """
        if not daily_costs:
            return {
                "alert": False,
                "reason": "No data provided",
                "latest": 0.0,
                "avg_7d": 0.0,
            }

        latest = daily_costs[-1]

        # If only one entry, the window IS that entry — can't be > 2x itself
        if len(daily_costs) == 1:
            return {
                "alert": False,
                "reason": "Insufficient history for anomaly detection",
                "latest": latest,
                "avg_7d": latest,
            }

        # Use last 7 entries excluding the latest as the rolling window
        window = daily_costs[:-1][-7:]
        avg_7d = sum(window) / len(window)

        if latest > 2 * avg_7d:
            alert = True
            reason = f"Latest cost {latest:.4f} exceeds 2x 7-day average {avg_7d:.4f}"
        else:
            alert = False
            reason = f"Latest cost {latest:.4f} within normal range (2x avg: {2 * avg_7d:.4f})"

        return {
            "alert": alert,
            "reason": reason,
            "latest": latest,
            "avg_7d": round(avg_7d, 6),
        }
