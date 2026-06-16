import re
from pathlib import Path

from promptwise.config import AppConfig, ModelPricing
from promptwise.types import RouteResult

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_OPUS_MODEL = "claude-opus-4-7"
_DEFAULT_MODEL = "claude-sonnet-4-6"
_ALL_MODELS = [_OPUS_MODEL, _DEFAULT_MODEL, _HAIKU_MODEL]

_PLUGIN_RULES: list[tuple[str, list[str]]] = [
    ("monitoring", ["cost", "burn", "budget", "overspend", "track"]),
    ("codereview_bridge", [r"\.py\b", r"\.js\b", r"\.go\b", "code review", "review.*file"]),
    ("playwright_bridge", [r"\.jsx\b", r"\.tsx\b", r"\.html\b", "visual test", "react component", "frontend"]),
]


class Router:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()

    def route(self, text: str, intent: str = "auto", stakes: str = "auto", provider: str = "claude",
              monthly_budget_usd: float | None = None, days_elapsed_in_month: int | None = None) -> RouteResult:
        intent = intent.lower() if intent != "auto" else self._detect_intent(text)
        stakes = stakes.lower() if stakes != "auto" else self._detect_stakes(text)
        provider = provider.lower()

        recommended = self._pick_model(intent, stakes, provider, monthly_budget_usd, days_elapsed_in_month)
        input_tokens = max(1, len(text) // 4)
        model = self.config.get_model(recommended)
        cost = input_tokens * model.rates.input_per_mtok / 1_000_000
        alt = [m for m in _ALL_MODELS if m != recommended]

        return RouteResult(
            recommended_model=recommended,
            reason=f"Routed to {recommended} based on intent={intent}, stakes={stakes}",
            intent_detected=intent,
            stakes_detected=stakes,
            estimated_input_cost_usd=round(cost, 8),
            context_window_pct=round(input_tokens / model.context_window * 100, 1),
            alternatives=alt,
            batch_recommended=intent in ("extract", "classify", "summarize"),
        )

    def compare_providers(self, text: str, model: str = _DEFAULT_MODEL) -> list[dict]:
        tokens = max(1, len(text) // 4)
        output_tokens = tokens * 2
        m = self.config.get_model(model)
        cost = tokens * m.rates.input_per_mtok / 1_000_000 + output_tokens * m.rates.output_per_mtok / 1_000_000
        return [{"provider": m.provider, "model": model, "total_cost_usd": round(cost, 8)}]

    def resolve_model(self, skill_name: str, budget_pct: float = 0.0) -> str:
        if budget_pct >= 95:
            return _HAIKU_MODEL
        if budget_pct >= 80:
            return _DEFAULT_MODEL
        return _DEFAULT_MODEL

    def route_for_plugin(self, text: str) -> str | None:
        text_lower = text.lower()
        for plugin_name, patterns in _PLUGIN_RULES:
            for pat in patterns:
                if re.search(pat, text_lower):
                    return plugin_name
        return None

    def fallback_models(self, current: str) -> list[str]:
        return [m for m in _ALL_MODELS if m != current]

    def _detect_intent(self, text: str) -> str:
        t = text.lower()
        if any(kw in t for kw in ("extract", "parse", "pull", "get all")):
            return "extract"
        if any(kw in t for kw in ("classify", "categorize", "label", "tag")):
            return "classify"
        if any(kw in t for kw in ("summarize", "tl;dr", "brief", "summary")):
            return "summarize"
        if any(kw in t for kw in ("code", "function", "implement", "write a", "class", "def ")):
            return "code"
        if any(kw in t for kw in ("analyze", "compare", "why", "how does")):
            return "analysis"
        if any(kw in t for kw in ("research", "find", "search", "what is")):
            return "research"
        if any(kw in t for kw in ("loop", "iterate", "repeat", "batch")):
            return "agent_loop"
        if "?" in t:
            return "question"
        return "auto"

    def _detect_stakes(self, text: str) -> str:
        t = text.lower()
        if any(kw in t for kw in ("production", "deploy", "customer", "revenue", "security", "critical")):
            return "high"
        if any(kw in t for kw in ("test", "draft", "wip", "idea", "maybe", "rough")):
            return "low"
        return "medium"

    def _pick_model(self, intent: str, stakes: str, provider: str,
                    monthly_budget_usd: float | None, days_elapsed: int | None) -> str:
        if stakes == "high" and intent in ("analysis", "code", "research", "agent_loop"):
            return self.config.providers.get(provider, ProviderConfig()).powerful if provider in self.config.providers else _OPUS_MODEL
        if intent in ("extract", "classify", "summarize", "question"):
            return self.config.providers.get(provider, ProviderConfig()).fast if provider in self.config.providers else _HAIKU_MODEL
        return self.config.providers.get(provider, ProviderConfig()).balanced if provider in self.config.providers else _DEFAULT_MODEL
