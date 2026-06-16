class CLIDashboard:
    def render_budget(self, used_usd: float, limit_usd: float, daily_burn: float, projected: float, alert: str) -> str:
        pct = round(used_usd / limit_usd * 100, 1) if limit_usd else 0
        markers = {"ok": "[OK]", "warn": "[!]", "critical": "[!!]", "hard_stop": "[STOP]"}
        marker = markers.get(alert, "[?]")
        lines = [
            "+-- Budget Status ----------------------------+",
            f"| Used: ${used_usd:.4f} / ${limit_usd:.2f} ({pct}%) {marker}",
            f"| Daily burn: ${daily_burn:.4f}/day",
            f"| Projected: ${projected:.2f}/month",
            f"| Alert: {alert.upper()}",
            "+-------------------------------------------+",
        ]
        return "\n".join(lines)

    def render_tasks(self, tasks: list[dict]) -> str:
        header = f"{'ID':<6} {'Action':<12} {'Status':<14} {'Cost USD':<10}"
        rows = [header, "-" * len(header)]
        for t in tasks:
            rows.append(f"{t['id']:<6} {t['action']:<12} {t['status']:<14} ${t.get('cost_usd', 0):.4f}")
        return "\n".join(rows)

    def render_plugins(self, plugins: list[dict]) -> str:
        lines = ["-- Plugins ------------------------"]
        for p in plugins:
            status = "[ACTIVE]" if p.get("active") else "[idle]"
            lines.append(f"  {p['name']:<25} {status}")
        return "\n".join(lines)

    def render_burn_rate(self, rate_usd_per_min: float) -> str:
        bar = "|" * min(40, int(rate_usd_per_min * 100))
        return f"Burn Rate: ${rate_usd_per_min:.4f}/min  [{bar:<40}]"
