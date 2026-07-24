"""external_pricing -- advisory-only reference pricing for non-Claude
providers (OpenAI/Gemini/etc.), used solely by compare_providers to show a
cost comparison. Deliberately decoupled from ModelRegistry/Router.route():
nothing in the real routing path imports this module, so it can never
influence which model Claude Code actually calls.

Offline-first, same contract as core/model_registry.py -- reads a local
YAML file, never fetches live. See
docs/superpowers/specs/2026-07-24-cross-provider-routing-design.md.
"""
from __future__ import annotations

from pathlib import Path


def _catalog_paths() -> list[Path]:
    return [
        Path("config") / "external_models.yaml",
        Path(__file__).resolve().parents[3] / "config" / "external_models.yaml",
    ]


class ExternalPricingCatalog:
    def __init__(self, path: str | Path | None = None):
        self._models: list[dict] = []
        self.loaded = False
        self._load(path)

    def _load(self, path: str | Path | None) -> None:
        candidates = [Path(path)] if path else _catalog_paths()
        for p in candidates:
            try:
                if not p.exists():
                    continue
                import yaml
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            models = data.get("models") or []
            if not isinstance(models, list):
                continue
            self._models = [
                m for m in models
                if isinstance(m, dict) and m.get("provider") and m.get("model")
                and m.get("input_per_mtok") is not None and m.get("output_per_mtok") is not None
            ]
            self.loaded = True
            break

    def all(self) -> list[dict]:
        return list(self._models)

    def for_tier(self, tier: str) -> list[dict]:
        tier = (tier or "").lower()
        return [m for m in self._models if str(m.get("tier", "")).lower() == tier]
