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
