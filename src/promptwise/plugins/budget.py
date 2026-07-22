import json
from pathlib import Path

from promptwise.config import AppConfig
from promptwise.core.model_registry import ModelRegistry
from promptwise.types import BudgetStatus

try:  # PyYAML is already a PromptWise dependency (policy/model registry/governor use it)
    import yaml
except Exception:  # pragma: no cover - yaml always present in practice
    yaml = None  # type: ignore

# Gitignored overlay the Phase-9 governor writes on an ``AdjustBudgetGuard`` apply
# (see core/governor: ``_BUDGET_OVERLAY``/``write_budget_overlay``). We mirror its
# location + YAML shape here WITHOUT importing the governor (avoids a plugin->core
# import cycle): a ``.promptwise/budget.local.yaml`` holding a ``limit_usd`` key.
_BUDGET_OVERLAY = "budget.local.yaml"
_DEFAULT_LIMIT_USD = 10.0


def _state_dir() -> Path:
    """Resolve the local ``.promptwise/`` state dir the SAME way the DB layer does,
    so we read the overlay from the exact place the governor writes it. Resolver is
    a seam tests monkeypatch to avoid touching the real ``~/.promptwise``."""
    from promptwise.db.models import get_db_path
    return get_db_path().parent


def _overlay_path() -> Path:
    return _state_dir() / _BUDGET_OVERLAY


def read_budget_overlay() -> float | None:
    """Return the overlaid budget limit (USD) or ``None`` when no usable overlay
    exists. Fail-soft: a missing/malformed/unparseable overlay yields ``None`` —
    never raises."""
    try:
        p = _overlay_path()
        if not p.exists():
            return None
        text = p.read_text(encoding="utf-8")
        if yaml is not None:
            data = yaml.safe_load(text) or {}
        else:  # pragma: no cover - yaml always present in practice
            data = json.loads(text)
        val = data.get("limit_usd") if isinstance(data, dict) else None
        return float(val) if val is not None else None
    except Exception:
        return None


def effective_limit(explicit: float | None) -> float:
    """The limit to enforce: an explicit caller-supplied value always wins; when
    none was passed, fall back to the governor overlay, else the built-in default."""
    if explicit is not None:
        return explicit
    overlay = read_budget_overlay()
    return overlay if overlay is not None else _DEFAULT_LIMIT_USD


# Bare tier/family words predict_cost has always accepted alongside a concrete
# alias (e.g. ``model="haiku"``) -> the registry tier they resolve to.
_FAMILY_TIER = {"haiku": "fast", "sonnet": "balanced", "opus": "powerful"}
# Registry tier -> the tier-name vocabulary this repo's guardrails allow
# (sonnet/opus/haiku), for the human-facing ``recommendation`` label only. The
# actual cost math never uses this table -- it reads live registry/config price.
_TIER_LABELS = {"fast": "haiku", "balanced": "sonnet", "powerful": "opus"}


class BudgetGuardian:
    def __init__(self, limit_usd: float | None = None, team_budget_usd: float = 100.0,
                 config: "AppConfig | None" = None, registry: "ModelRegistry | None" = None):
        # ``limit_usd is None`` marks "caller relied on the default" -> read the
        # governor overlay (closing the loop) and fall back to _DEFAULT_LIMIT_USD.
        # An explicit ``limit_usd=X`` still wins, preserving existing callers.
        limit = effective_limit(limit_usd)
        self.limit_usd = limit
        self.team_budget_usd = team_budget_usd
        self._limits: dict[str, float] = {"monthly": limit}
        self._current_spend = 0.0
        self._daily_burn = 0.0
        # Pricing source for predict_cost: registry first (the live source
        # core/router.py already reads), config second, RateSpec defaults last --
        # same fallback chain as Router._input_rate, so the two engines can never
        # drift out of sync again (see docs/GAP_ANALYSIS_2026-07.md section 3).
        self._config = config or AppConfig()
        self._registry = registry or ModelRegistry()

    def check(self, used_usd: float, days_elapsed: int, project_id: str | None = None,
              tool_cost_usd: float = 0.0) -> BudgetStatus:
        """``used_usd`` is the LLM token-cost leg; ``tool_cost_usd`` is an optional
        second leg for tool/API execution cost incurred by the same workflow
        (Phase 14 workflow-level cost attribution -- LangSmith attributes both).
        Every existing caller omits ``tool_cost_usd`` and sees identical output:
        the total collapses to ``used_usd`` and ``cost_breakdown`` stays ``None``."""
        total = used_usd + tool_cost_usd
        pct = round(total / self.limit_usd * 100, 1) if self.limit_usd else 0.0
        daily_burn = round(total / max(days_elapsed, 1), 4)
        projected = round(daily_burn * 30, 4)

        if total >= self.limit_usd:
            alert = "hard_stop"
        elif pct >= 90:
            alert = "critical"
        elif pct >= 70:
            alert = "warn"
        else:
            alert = "ok"

        breakdown = {"llm_usd": round(used_usd, 6), "tool_usd": round(tool_cost_usd, 6)} if tool_cost_usd else None
        return BudgetStatus(used_usd=round(total, 4), limit_usd=self.limit_usd, pct_used=pct,
                            daily_burn_usd=daily_burn, projected_monthly_usd=projected,
                            alert_level=alert, project_id=project_id, cost_breakdown=breakdown)

    def _resolve_alias(self, model: str) -> str:
        """Accept either a concrete alias or a bare family/tier word (haiku/sonnet/
        opus) for backward compatibility with predict_cost's original leniency."""
        if self._registry.tier_of(model) or model in self._config.models:
            return model
        ml = model.lower()
        for fam, tier in _FAMILY_TIER.items():
            if fam in ml:
                resolved = self._registry.resolve(tier, "claude")
                if resolved:
                    return resolved
        return model

    def _model_rates(self, alias: str) -> tuple[float, float]:
        """(input_per_mtok, output_per_mtok) -- registry price first (the live
        source), then config pricing, then RateSpec defaults. Mirrors
        Router._input_rate exactly so the two engines never drift again."""
        pr = self._registry.price(alias)
        cfg = self._config.get_model(alias)
        # See Router._input_rate: a present-but-null price field in models.yaml
        # must fall back to config pricing rather than reach float() as None.
        pr_in = pr.get("input_per_mtok") if pr else None
        pr_out = pr.get("output_per_mtok") if pr else None
        in_rate = pr_in if pr_in is not None else cfg.rates.input_per_mtok
        out_rate = pr_out if pr_out is not None else cfg.rates.output_per_mtok
        return float(in_rate), float(out_rate)

    def predict_cost(self, prompt: str, model: str = "claude-sonnet-4-6") -> dict:
        alias = self._resolve_alias(model)
        in_rate, out_rate = self._model_rates(alias)
        inp = max(1, len(prompt) // 4)
        out = inp * 2
        cost = inp * in_rate / 1_000_000 + out * out_rate / 1_000_000
        tier = self._registry.tier_of(alias) or self._config.get_model(alias).tier or "balanced"
        label = _TIER_LABELS.get(tier, tier)
        return {"estimated_input_tokens": inp, "estimated_output_tokens": out, "estimated_cost_usd": round(cost, 8),
                "model": model, "recommendation": "haiku" if cost > self.limit_usd * 0.1 else label}

    def set_limit(self, limit_usd: float, period: str = "monthly") -> None:
        self._limits[period] = limit_usd
        if period == "monthly":
            self.limit_usd = limit_usd

    def get_budget_status(self, current_spend_usd: float | None = None,
                           daily_burn_usd: float | None = None) -> dict:
        """``current_spend_usd``/``daily_burn_usd`` let the caller supply real,
        month-to-date numbers (read from cost_logs); omitting them preserves the
        prior zero-init default for any caller that never fed ``check()``."""
        spend = self._current_spend if current_spend_usd is None else current_spend_usd
        burn = self._daily_burn if daily_burn_usd is None else daily_burn_usd
        limit = self._limits.get("monthly", self.limit_usd)
        pct = round(spend / limit * 100, 2) if limit > 0 else 0.0
        days = round((limit - spend) / burn, 1) if burn > 0 else None
        return {"limit_usd": limit, "period": "monthly", "current_spend_usd": round(spend, 6),
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
