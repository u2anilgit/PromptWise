import os
import re
from dataclasses import dataclass, field

from promptwise.config import AppConfig
from promptwise.core.adaptive_router import AdaptiveRouter
from promptwise.core.model_registry import ModelRegistry
from promptwise.types import RouteResult

# Adaptive routing is on by default; these values disable it (fail-open to static).
_ADAPTIVE_OFF = ("0", "off", "false", "no")


@dataclass
class EmissionPlan:
    """What to emit, derived from prompt intent (config-compiler helper)."""
    intent: str
    sections: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)


# No concrete model id is hardcoded in this engine. Routing resolves a *tier*
# (fast / balanced / powerful) to a concrete alias via the model registry
# (config/models.yaml), falling back to the provider tiers / default model in
# config. A new model going live is a one-row registry edit, not a code change.

_PLUGIN_RULES: list[tuple[str, list[str]]] = [
    ("monitoring", ["cost", "burn", "budget", "overspend", "track"]),
    ("codereview_bridge", [r"\.py\b", r"\.js\b", r"\.go\b", "code review", "review.*file"]),
    ("playwright_bridge", [r"\.jsx\b", r"\.tsx\b", r"\.html\b", "visual test", "react component", "frontend"]),
]


class Router:
    def __init__(self, config: AppConfig | None = None, registry: ModelRegistry | None = None,
                 adaptive: "AdaptiveRouter | None" = None):
        self.config = config or AppConfig()
        self.registry = registry or ModelRegistry()
        # Lazily built on first adaptive route so a Router that never routes
        # (or runs with the flag off) never touches the outcome store.
        self._adaptive = adaptive
        self._adaptive_built = adaptive is not None

    # ── tier resolution (registry first, then config, never a code literal) ──
    def _provider_key(self, provider: str) -> str | None:
        provider = (provider or "").lower()
        if provider in self.config.providers:
            return provider
        for key, pc in self.config.providers.items():
            if provider == key.lower() or provider in [a.lower() for a in (pc.aliases or [])]:
                return key
        return None

    def _tier_model(self, tier: str, provider: str = "claude") -> str:
        """Resolve a tier to a concrete alias: newest current in the registry,
        else the provider's configured tier, else the default model."""
        alias = self.registry.resolve(tier, provider)
        if alias:
            return alias
        key = self._provider_key(provider)
        if key and key in self.config.providers:
            pc = self.config.providers[key]
            return {"fast": pc.fast, "balanced": pc.balanced, "powerful": pc.powerful}.get(
                tier, self.config.default_model)
        return self.config.default_model

    def _provider_cap(self, provider: str) -> float | None:
        """Configured hard spend cap for a provider (``daily_cap_usd``), or
        ``None`` when unlimited/unconfigured -- opt-in, no behavior change unless
        a phase-14 ``daily_cap_usd`` row is present in ``config/promptwise.yaml``."""
        key = self._provider_key(provider)
        if key and key in self.config.providers:
            return self.config.providers[key].daily_cap_usd
        return None

    def _current_models(self) -> list[str]:
        """Selectable current models (for alternatives / fallbacks)."""
        if self.registry.loaded:
            cur = self.registry.all_current()
            if cur:
                return cur
        seen: list[str] = []
        for t in ("powerful", "balanced", "fast"):
            m = self._tier_model(t)
            if m and m not in seen:
                seen.append(m)
        return seen or [self.config.default_model]

    def _input_rate(self, model_alias: str) -> tuple[float, int]:
        """(input_per_mtok, context_window) for a model — registry price first
        (the live source), then config pricing, then defaults."""
        pr = self.registry.price(model_alias)
        cfg = self.config.get_model(model_alias)
        rate = pr.get("input_per_mtok") if pr and "input_per_mtok" in pr else cfg.rates.input_per_mtok
        return float(rate), int(cfg.context_window)

    def route(self, text: str, intent: str = "auto", stakes: str = "auto", provider: str = "claude",
              monthly_budget_usd: float | None = None, days_elapsed_in_month: int | None = None,
              provider_spend_usd: float | None = None) -> RouteResult:
        intent = intent.lower() if intent != "auto" else self._detect_intent(text)
        stakes = stakes.lower() if stakes != "auto" else self._detect_stakes(text)
        provider = provider.lower()

        static_tier = self._static_tier(intent, stakes)
        tier, adaptive_note = self._maybe_adapt(intent, stakes, static_tier)

        # Provider-level hard budget cap (LiteLLM provider_budget_routing analogue):
        # once the caller-reported spend for this provider hits its configured cap,
        # refuse the computed tier and reroute to the cheapest one BEFORE the call
        # is made. Fail-open: no cap configured, or no spend figure supplied -> no
        # enforcement, byte-for-byte identical to pre-Phase-14 routing.
        cap = self._provider_cap(provider)
        provider_capped = cap is not None and provider_spend_usd is not None and provider_spend_usd >= cap
        if provider_capped:
            tier = "fast"

        recommended = self._resolve_current(tier, provider)
        input_tokens = max(1, len(text) // 4)
        in_rate, ctx_window = self._input_rate(recommended)
        cost = input_tokens * in_rate / 1_000_000
        alt = [m for m in self._current_models() if m != recommended]

        reason = f"Routed to {recommended} based on intent={intent}, stakes={stakes}"
        if adaptive_note:
            reason += f" | adaptive: {adaptive_note}"
        if provider_capped:
            reason += (f" | provider '{provider}' hard budget cap reached "
                       f"(${provider_spend_usd:.2f} >= ${cap:.2f}) -- rerouted to fast tier")

        return RouteResult(
            recommended_model=recommended,
            reason=reason,
            intent_detected=intent,
            stakes_detected=stakes,
            estimated_input_cost_usd=round(cost, 8),
            context_window_pct=round(input_tokens / ctx_window * 100, 1),
            alternatives=alt,
            batch_recommended=intent in ("extract", "classify", "summarize"),
            provider_capped=provider_capped,
        )

    def compare_providers(self, text: str, model: str | None = None) -> list[dict]:
        model = model or self.config.default_model
        tokens = max(1, len(text) // 4)
        output_tokens = tokens * 2
        m = self.config.get_model(model)
        pr = self.registry.price(model)
        in_rate = pr.get("input_per_mtok") if pr and "input_per_mtok" in pr else m.rates.input_per_mtok
        out_rate = pr.get("output_per_mtok") if pr and "output_per_mtok" in pr else m.rates.output_per_mtok
        cost = tokens * float(in_rate) / 1_000_000 + output_tokens * float(out_rate) / 1_000_000
        return [{"provider": m.provider, "model": model, "total_cost_usd": round(cost, 8)}]

    def resolve_model(self, skill_name: str, budget_pct: float = 0.0) -> str:
        if budget_pct >= 95:
            return self._tier_model("fast")
        return self._tier_model("balanced")

    def route_for_plugin(self, text: str) -> str | None:
        text_lower = text.lower()
        for plugin_name, patterns in _PLUGIN_RULES:
            for pat in patterns:
                if re.search(pat, text_lower):
                    return plugin_name
        return None

    def fallback_models(self, current: str) -> list[str]:
        return [m for m in self._current_models() if m != current]

    def plan_emission(self, text: str) -> "EmissionPlan":
        """Map a prompt's intent onto which config sections matter most.

        Additive helper for the cross-agent config compiler; ``route()`` is
        unchanged. Targets default to AGENTS.md-first (the shared base most
        agents read), with the detector free to widen them later.
        """
        intent = self._detect_intent(text)
        sections = ["method", "policy", "house_rules"]
        if intent in ("code", "analysis"):
            sections = ["commands", "policy", "method", "house_rules"]
        elif intent in ("research", "question"):
            sections = ["method", "policy"]
        return EmissionPlan(intent=intent, sections=sections, targets=["codex"])

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

    # ── static tier heuristic (the always-available default) ─────────────────
    def _static_tier(self, intent: str, stakes: str) -> str:
        if stakes == "high" and intent in ("analysis", "code", "research", "agent_loop"):
            return "powerful"
        if intent in ("extract", "classify", "summarize", "question"):
            return "fast"
        return "balanced"

    def _pick_model(self, intent: str, stakes: str, provider: str,
                    monthly_budget_usd: float | None, days_elapsed: int | None) -> str:
        # Retained for backward compatibility: pure static pick, no history.
        return self._tier_model(self._static_tier(intent, stakes), provider)

    def _resolve_current(self, tier: str, provider: str) -> str:
        """Resolve a tier to a concrete alias, never a deprecated one. The
        registry already returns current-only; this also guards the config
        fallback path (which could name a retired alias)."""
        alias = self._tier_model(tier, provider)
        if self.registry.loaded and self.registry.is_deprecated(alias):
            cur = self.registry.resolve(tier, provider)
            if cur:
                alias = cur
        return alias

    # ── adaptive blend (env-gated, fail-open to static on ANY error) ─────────
    def _maybe_adapt(self, intent: str, stakes: str, static_tier: str) -> tuple[str, str]:
        if os.environ.get("PROMPTWISE_ADAPTIVE_ROUTING", "on").strip().lower() in _ADAPTIVE_OFF:
            return static_tier, ""
        try:
            if not self._adaptive_built:
                self._adaptive = AdaptiveRouter()
                self._adaptive_built = True
            scorer = self._adaptive
            if scorer is None:
                return static_tier, ""
            task_class = f"{intent}/{stakes}"
            tier, note = scorer.adapt(task_class, static_tier)
            return (tier or static_tier), (note or "")
        except Exception:
            return static_tier, ""
