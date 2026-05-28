from promptwise_v2.types_v2 import BudgetStatus


class BudgetGuardian:
    def __init__(self, limit_usd: float = 10.0, team_budget_usd: float = 100.0):
        self.limit_usd = limit_usd
        self.team_budget_usd = team_budget_usd

    def check(self, used_usd: float, days_elapsed: int) -> BudgetStatus:
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
        )
