"""RouterV2 — model routing with YAML-driven strategy.

Loads config/model_strategy.yaml on init; falls back to hardcoded
defaults if the file is not found or cannot be parsed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
    _YAML_AVAILABLE = True
except ImportError:  # pragma: no cover
    _YAML_AVAILABLE = False

# ---------------------------------------------------------------------------
# Hardcoded fallback defaults (used when YAML is absent or yaml lib missing)
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "claude-sonnet-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"
OPUS_MODEL = "claude-opus-4-7"

_ALL_MODELS = [OPUS_MODEL, DEFAULT_MODEL, HAIKU_MODEL]

# ---------------------------------------------------------------------------
# Plugin routing rules (unchanged from original)
# ---------------------------------------------------------------------------
_PLUGIN_RULES: list[tuple[str, list[str]]] = [
    ("monitoring",        ["cost", "burn", "budget", "overspend", "track"]),
    ("codereview_bridge", [r"\.py\b", r"\.js\b", r"\.go\b", "code review", "review.*file"]),
    ("playwright_bridge", [r"\.jsx\b", r"\.tsx\b", r"\.html\b", "visual test", "react component",
                           "frontend"]),
]

# ---------------------------------------------------------------------------
# Auto-discovery: walk up from this file to find config/model_strategy.yaml
# ---------------------------------------------------------------------------
def _find_default_config() -> Path | None:
    here = Path(__file__).resolve()
    for parent in [here.parent, here.parent.parent, here.parent.parent.parent,
                   here.parent.parent.parent.parent]:
        candidate = parent / "config" / "model_strategy.yaml"
        if candidate.exists():
            return candidate
    return None


class RouterV2:
    """Route requests to the appropriate model based on skill and budget."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._strategy = self._load_strategy(config_path)

    # ------------------------------------------------------------------
    # Strategy loading
    # ------------------------------------------------------------------
    def _load_strategy(self, config_path: Path | None) -> dict[str, Any]:
        path = config_path or _find_default_config()
        if path is None or not Path(path).exists():
            return self._default_strategy()
        if not _YAML_AVAILABLE:
            return self._default_strategy()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if not isinstance(data, dict):
                return self._default_strategy()
            return data
        except Exception:
            return self._default_strategy()

    @staticmethod
    def _default_strategy() -> dict[str, Any]:
        return {
            "default_model": DEFAULT_MODEL,
            "routing_rules": {
                "opus":   {"skills": []},
                "sonnet": {"skills": []},
                "haiku":  {"skills": []},
            },
            "cost_safety": {
                "downgrade_at_budget_pct": 80,
                "emergency_haiku_pct": 95,
                "hard_stop_pct": 100,
                "never_downgrade": [],
            },
            "context_routing": {
                "large_context_threshold": 50000,
                "large_context_model": DEFAULT_MODEL,
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _default_model(self) -> str:
        return self._strategy.get("default_model", DEFAULT_MODEL)

    def _routing_rules(self) -> dict[str, Any]:
        return self._strategy.get("routing_rules", {})

    def _cost_safety(self) -> dict[str, Any]:
        return self._strategy.get("cost_safety", {})

    def _context_routing(self) -> dict[str, Any]:
        return self._strategy.get("context_routing", {})

    def _natural_model_for_skill(self, skill_name: str) -> str:
        """Return the model tier assigned to *skill_name* in routing_rules."""
        rules = self._routing_rules()

        # Check opus
        opus_skills: list[str] = rules.get("opus", {}).get("skills", []) or []
        if skill_name in opus_skills:
            return OPUS_MODEL

        # Check haiku
        haiku_skills: list[str] = rules.get("haiku", {}).get("skills", []) or []
        if skill_name in haiku_skills:
            return HAIKU_MODEL

        # Check sonnet
        sonnet_skills: list[str] = rules.get("sonnet", {}).get("skills", []) or []
        if skill_name in sonnet_skills:
            return DEFAULT_MODEL

        return self._default_model()

    # ------------------------------------------------------------------
    # Public API — new methods
    # ------------------------------------------------------------------
    def resolve_model(self, skill_name: str, budget_pct: float = 0.0) -> str:
        """Return the best model for *skill_name* given current budget usage.

        Logic (in priority order):
        1. If budget_pct >= emergency_haiku_pct  → always return haiku.
        2. If skill is in never_downgrade         → return its natural model.
        3. If budget_pct >= downgrade_at_budget_pct and natural model is opus
           → downgrade to sonnet.
        4. Return natural model from routing_rules.
        5. Default: return default_model.
        """
        cs = self._cost_safety()
        emergency_pct: float = cs.get("emergency_haiku_pct", 95)
        downgrade_pct: float = cs.get("downgrade_at_budget_pct", 80)
        never_downgrade: list[str] = cs.get("never_downgrade", []) or []

        # Rule 1 — emergency haiku threshold
        if budget_pct >= emergency_pct:
            return HAIKU_MODEL

        natural = self._natural_model_for_skill(skill_name)

        # Rule 2 — never downgrade safety-critical skills
        if skill_name in never_downgrade:
            return natural

        # Rule 3 — downgrade opus→sonnet at budget threshold
        if budget_pct >= downgrade_pct and natural == OPUS_MODEL:
            return DEFAULT_MODEL

        return natural

    def apply_context_routing(self, token_count: int) -> str:
        """Return the appropriate model based on context (token) size."""
        cr = self._context_routing()
        threshold: int = cr.get("large_context_threshold", 50000)
        large_model: str = cr.get("large_context_model", self._default_model())

        if token_count > threshold:
            return large_model
        return self._default_model()

    # ------------------------------------------------------------------
    # Original methods (unchanged behaviour)
    # ------------------------------------------------------------------
    def route_for_plugin(self, text: str) -> str | None:
        text_lower = text.lower()
        for plugin_name, patterns in _PLUGIN_RULES:
            for pat in patterns:
                if re.search(pat, text_lower):
                    return plugin_name
        return None

    def fallback_models(self, current: str) -> list[str]:
        return [m for m in _ALL_MODELS if m != current]
