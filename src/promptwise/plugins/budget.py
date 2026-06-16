from promptwise.types import BudgetStatus


class BudgetGuardian:
    def __init__(self, limit_usd: float = 10.0, team_budget_usd: float = 100.0):
        self.limit_usd = limit_usd
        self.team_budget_usd = team_budget_usd
        self._limits: dict[str, float] = {"monthly": limit_usd}
        self._current_spend = 0.0
        self._daily_burn = 0.0

    def check(self, used_usd: float, days_elapsed: int, project_id: str | None = None) -> BudgetStatus:
        pct = round(used_usd / self.limit_usd * 100, 1) if self.limit_usd else 0.0
        daily_burn = round(used_usd / max(days_elapsed, 1), 4)
        projected = round(daily_burn * 30, 4)

        if used_usd >= self.limit_usd:
            alert = "hard_stop"
        elif pct >= 90:
            alert = "critical"
        elif pct >= 70:
            alert = "warn"
        else:
            alert = "ok"

        return BudgetStatus(used_usd=round(used_usd, 4), limit_usd=self.limit_usd, pct_used=pct,
                            daily_burn_usd=daily_burn, projected_monthly_usd=projected,
                            alert_level=alert, project_id=project_id)

    def predict_cost(self, prompt: str, model: str = "claude-sonnet-4-6") -> dict:
        pricing = {"haiku": {"input": 0.8, "output": 4.0}, "sonnet": {"input": 3.0, "output": 15.0}, "opus": {"input": 15.0, "output": 75.0}}
        ml = model.lower()
        tier = "haiku" if "haiku" in ml else ("opus" if "opus" in ml else "sonnet")
        p = pricing[tier]
        inp = max(1, len(prompt) // 4)
        out = inp * 2
        cost = inp * p["input"] / 1_000_000 + out * p["output"] / 1_000_000
        return {"estimated_input_tokens": inp, "estimated_output_tokens": out, "estimated_cost_usd": round(cost, 8),
                "model": model, "recommendation": "haiku" if cost > self.limit_usd * 0.1 else tier}

    def set_limit(self, limit_usd: float, period: str = "monthly") -> None:
        self._limits[period] = limit_usd
        if period == "monthly":
            self.limit_usd = limit_usd

    def get_budget_status(self) -> dict:
        limit = self._limits.get("monthly", self.limit_usd)
        pct = round(self._current_spend / limit * 100, 2) if limit > 0 else 0.0
        days = round((limit - self._current_spend) / self._daily_burn, 1) if self._daily_burn > 0 else None
        return {"limit_usd": limit, "period": "monthly", "current_spend_usd": round(self._current_spend, 6),
                "pct_used": pct, "days_remaining_at_burn_rate": days}

    def cost_anomaly_detect(self, daily_costs: list[float]) -> dict:
        if not daily_costs:
            return {"alert": False, "reason": "No data", "latest": 0.0, "avg_7d": 0.0}
        latest = daily_costs[-1]
        if len(daily_costs) == 1:
            return {"alert": False, "reason": "Insufficient history", "latest": latest, "avg_7d": latest}
        window = daily_costs[:-1][-7:]
        avg = sum(window) / len(window)
        alert = latest > 2 * avg
        return {"alert": alert, "reason": f"Latest {latest:.4f} {'exceeds' if alert else 'within'} 2x avg {avg:.4f}",
                "latest": latest, "avg_7d": round(avg, 6)}
