"""Model routing based on intent, stakes, and budget."""

import re
from typing import Optional

from promptwise.config import AppConfig
from promptwise.tokenizer import count_tokens
from promptwise.types import RouteResult


class Router:
    """Route requests to appropriate model tier."""

    INTENT_KEYWORDS = {
        "extract": [
            "extract",
            "pull",
            "list",
            "enumerate",
            "find all",
        ],
        "classify": ["classify", "categorize", "label", "tag", "type"],
        "summarize": [
            "summarize",
            "summary",
            "brief",
            "tldr",
            "condense",
        ],
        "question": ["what", "when", "where", "why", "how", "explain", "describe"],
        "code": [
            "code",
            "function",
            "refactor",
            "debug",
            "fix",
            "implement",
            "script",
        ],
        "analysis": ["analyze", "metric", "performance", "data", "trend", "report"],
        "agent_loop": ["step", "chain", "loop", "iterate", "multi-step", "then"],
        "research": [
            "research",
            "investigate",
            "explore",
            "compare",
            "synthesis",
            "novel",
        ],
    }

    STAKES_HIGH = ["production", "compliance", "legal", "patient", "financial"]
    STAKES_LOW = ["test", "scratch", "playground", "demo"]

    TOOL_CHAIN_KEYWORDS = ["read", "edit", "run", "test", "commit", "deploy"]

    DEFAULT_TIERS = {
        "extract": "fast",
        "classify": "fast",
        "summarize": "fast",
        "question": "balanced",
        "code": "balanced",
        "analysis": "balanced",
        "agent_loop": "balanced",
        "research": "powerful",
    }

    TASK_BUDGETS = {
        "extract": 2000,
        "classify": 2000,
        "summarize": 2000,
        "question": 2000,
        "code": 8000,
        "analysis": 8000,
        "agent_loop": 32000,
        "research": 64000,
    }

    def __init__(self, config: AppConfig):
        """Initialize router with config.

        Args:
            config: AppConfig with pricing
        """
        self.config = config

    def route(
        self,
        text: str,
        intent: str = "auto",
        stakes: str = "auto",
        provider: str = "claude",
        monthly_budget_usd: Optional[float] = None,
        days_elapsed_in_month: Optional[int] = None,
    ) -> RouteResult:
        """Route request to appropriate model.

        Args:
            text: Request text
            intent: Intent keyword or "auto"
            stakes: "low"|"medium"|"high" or "auto"
            provider: Provider name
            monthly_budget_usd: Monthly budget for guardrails
            days_elapsed_in_month: Days elapsed for burn-rate calc

        Returns:
            RouteResult with recommendation
        """
        input_tokens = count_tokens(text, "claude-sonnet-4-6").value

        if intent == "auto":
            intent = self._detect_intent(text)

        if stakes == "auto":
            stakes = self._detect_stakes(text)

        tool_chain_depth = self._count_tool_chain_mentions(text)

        tier = self.DEFAULT_TIERS.get(intent, "balanced")

        if intent == "summarize" and input_tokens > 100000:
            tier = "balanced"
        elif intent == "code" and (
            "multi-file" in text.lower() or tool_chain_depth >= 3
        ):
            tier = "powerful"
        elif intent == "agent_loop" and tool_chain_depth > 5:
            tier = "powerful"

        if stakes == "high":
            tier = "powerful"
        elif stakes == "low" and tier == "balanced":
            tier = "fast"

        model_id = self.config.providers.providers[provider].tiers.model_dump()[
            tier
        ]
        model_config = self.config.pricing.models.get(model_id)
        display_name = model_config.display_name if model_config else model_id

        estimated_input_cost = self._estimate_cost(input_tokens, model_id)
        estimated_output_tokens = int(input_tokens * 0.2)
        estimated_output_cost = self._estimate_output_cost(estimated_output_tokens, model_id)

        context_window = model_config.context_window if model_config else 200000
        context_window_pct = round(input_tokens / context_window * 100, 1)
        context_window_warning = None
        if context_window_pct > 80:
            context_window_warning = (
                f"Input uses {context_window_pct}% of {model_id} context window "
                f"({context_window:,} tokens). Consider optimize_context first."
            )
        elif context_window_pct > 100:
            context_window_warning = (
                f"Input EXCEEDS {model_id} context window ({context_window:,} tokens). "
                "Request will fail. Use optimize_context or switch to a larger-context model."
            )

        reason = f"Intent: {intent}, Stakes: {stakes}, Tool chain: {tool_chain_depth}"

        task_budget = self.TASK_BUDGETS.get(intent, 2000)

        alternatives = self._get_alternatives(provider, tier, input_tokens)

        peak_hour_warning = None
        peak_hours = self.config.providers.providers[provider].peak_hours_utc
        if peak_hours:
            from datetime import datetime, timezone

            current_hour = datetime.now(timezone.utc).hour
            if current_hour in peak_hours:
                peak_hour_warning = f"Peak hours detected (UTC {current_hour})"

        cost_floor_breached = False
        if (
            monthly_budget_usd
            and days_elapsed_in_month
            and days_elapsed_in_month > 0
        ):
            daily_burn = (estimated_input_cost) / max(days_elapsed_in_month, 1)
            projected_monthly = daily_burn * 30
            if projected_monthly > monthly_budget_usd * 1.1:
                tier = self._downgrade_tier(tier)
                model_id = self.config.providers.providers[provider].tiers.model_dump()[
                    tier
                ]
                model_config = self.config.pricing.models.get(model_id)
                display_name = model_config.display_name if model_config else model_id
                estimated_input_cost = self._estimate_cost(input_tokens, model_id)
                estimated_output_cost = self._estimate_output_cost(estimated_output_tokens, model_id)
                cost_floor_breached = True

        batch_recommended = (
            intent in ("extract", "classify", "summarize")
            and stakes != "high"
        )

        return RouteResult(
            recommended_model=model_id,
            recommended_display=display_name,
            reason=reason,
            intent_detected=intent,
            stakes_detected=stakes,
            tool_chain_depth=tool_chain_depth,
            input_tokens=input_tokens,
            estimated_input_cost_usd=estimated_input_cost,
            estimated_output_cost_usd=estimated_output_cost,
            context_window_pct=context_window_pct,
            context_window_warning=context_window_warning,
            task_budget_recommended=task_budget,
            peak_hour_warning=peak_hour_warning,
            cost_floor_breached=cost_floor_breached,
            alternatives=alternatives,
            batch_recommended=batch_recommended,
        )

    def _detect_intent(self, text: str) -> str:
        """Detect intent from text keywords."""
        text_lower = text.lower()
        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return intent
        return "question"

    def _detect_stakes(self, text: str) -> str:
        """Detect stakes level from keywords."""
        text_lower = text.lower()
        if any(kw in text_lower for kw in self.STAKES_HIGH):
            return "high"
        if any(kw in text_lower for kw in self.STAKES_LOW):
            return "low"
        return "medium"

    def _count_tool_chain_mentions(self, text: str) -> int:
        """Count mentions of tool chain keywords."""
        text_lower = text.lower()
        count = sum(1 for kw in self.TOOL_CHAIN_KEYWORDS if kw in text_lower)
        return count

    def _estimate_cost(self, input_tokens: int, model_id: str) -> float:
        """Estimate input cost for request."""
        model = self.config.pricing.models.get(model_id)
        if not model:
            return 0.0
        rate_per_token = model.rates.input_per_mtok / 1_000_000
        return round(input_tokens * rate_per_token, 6)

    def _estimate_output_cost(self, output_tokens: int, model_id: str) -> float:
        """Estimate output cost (20% of input tokens heuristic)."""
        model = self.config.pricing.models.get(model_id)
        if not model:
            return 0.0
        rate_per_token = model.rates.output_per_mtok / 1_000_000
        return round(output_tokens * rate_per_token, 6)

    def _downgrade_tier(self, tier: str) -> str:
        """Downgrade tier one level."""
        tier_order = ["fast", "balanced", "powerful"]
        idx = tier_order.index(tier)
        return tier_order[max(0, idx - 1)]

    def compare_providers(self, text: str, model: str = "claude-sonnet-4-6") -> list[dict]:
        """Compare input+output cost for same text across all providers.

        Args:
            text: Request text
            model: Model for token counting

        Returns:
            List of provider comparisons sorted by input cost ascending
        """
        input_tokens = count_tokens(text, model).value
        estimated_output_tokens = int(input_tokens * 0.2)

        results = []
        for provider_name, provider_cfg in self.config.providers.providers.items():
            for tier_name, model_id in provider_cfg.tiers.model_dump().items():
                model_pricing = self.config.pricing.models.get(model_id)
                if not model_pricing:
                    continue
                input_cost = self._estimate_cost(input_tokens, model_id)
                output_cost = self._estimate_output_cost(estimated_output_tokens, model_id)
                context_window = model_pricing.context_window
                results.append({
                    "provider": provider_name,
                    "tier": tier_name,
                    "model": model_id,
                    "display": model_pricing.display_name,
                    "input_cost_usd": input_cost,
                    "output_cost_usd": output_cost,
                    "total_cost_usd": round(input_cost + output_cost, 6),
                    "context_window": context_window,
                    "fits_context": input_tokens <= context_window,
                    "pricing_note": model_pricing.notes if model_pricing.notes else None,
                })

        return sorted(results, key=lambda x: x["total_cost_usd"])

    def _get_alternatives(
        self, provider: str, current_tier: str, input_tokens: int
    ) -> list[dict]:
        """Get alternative tier recommendations."""
        tier_order = ["fast", "balanced", "powerful"]
        current_idx = tier_order.index(current_tier)

        alternatives = []
        for tier in tier_order:
            if tier == current_tier:
                continue
            model_id = self.config.providers.providers[provider].tiers.model_dump()[
                tier
            ]
            display = self.config.pricing.models[model_id].display_name
            cost = self._estimate_cost(input_tokens, model_id)
            current_cost = self._estimate_cost(
                input_tokens,
                self.config.providers.providers[provider]
                .tiers.model_dump()[current_tier],
            )
            delta_pct = (
                ((cost - current_cost) / current_cost * 100)
                if current_cost > 0
                else 0
            )
            alternatives.append(
                {
                    "model": model_id,
                    "display": display,
                    "input_cost": cost,
                    "delta_pct": delta_pct,
                }
            )

        return alternatives
