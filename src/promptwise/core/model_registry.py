"""model_registry — resolve a routing tier to the newest *current* model in a
family, from a config registry rather than hardcoded ids.

Routing logic asks for a **tier** (fast / balanced / powerful) and, optionally, a
provider or family; the registry returns the concrete alias. A new model going
live is one edited row in ``config/models.yaml`` — no code change, no branded id
frozen into the engine.

Design contract
---------------
* **Config is the source of truth.** No concrete model id is hardcoded here; if
  the registry file is absent, resolution returns ``None`` and the caller falls
  back to its own config (provider tiers / default model).
* **Deprecated is retained, not deleted.** A ``deprecated`` model is never
  *selected* by routing, but stays resolvable for historical labels and pricing.
* **Point-in-time pricing.** ``price(alias)`` returns the unit price recorded for
  that specific model, so a usage record can snapshot the price it actually paid
  and a later price change never rewrites history.
* **Offline-first.** Pure stdlib + PyYAML load; no network. An online refresh is
  a separate, opt-in concern that only rewrites this file.
"""
from __future__ import annotations

from pathlib import Path


def _registry_paths() -> list[Path]:
    return [
        Path("config") / "models.yaml",
        Path(__file__).resolve().parents[3] / "config" / "models.yaml",
    ]


class ModelRegistry:
    """Tier/family -> concrete alias resolver over ``config/models.yaml``."""

    def __init__(self, path: str | Path | None = None):
        self._families: dict[str, dict] = {}
        self._models: list[dict] = []
        self._by_alias: dict[str, dict] = {}
        self.loaded = False
        self._load(path)

    # ── loading ──────────────────────────────────────────────────────────────
    def _load(self, path: str | Path | None) -> None:
        candidates = [Path(path)] if path else _registry_paths()
        for p in candidates:
            try:
                if not p.exists():
                    continue
                import yaml
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            fams = data.get("families") or {}
            models = data.get("models") or []
            if not isinstance(fams, dict) or not isinstance(models, list):
                continue
            self._families = fams
            self._models = [m for m in models if isinstance(m, dict) and m.get("alias")]
            self._by_alias = {m["alias"]: m for m in self._models}
            self.loaded = True
            return

    # ── helpers ──────────────────────────────────────────────────────────────
    def _tier_of(self, model: dict) -> str:
        fam = self._families.get(model.get("family", ""), {})
        return str(model.get("tier") or fam.get("tier") or "")

    def _provider_of(self, model: dict) -> str:
        fam = self._families.get(model.get("family", ""), {})
        return str(model.get("provider") or fam.get("provider") or "")

    # ── resolution ───────────────────────────────────────────────────────────
    def resolve(self, tier: str, provider: str = "claude") -> str | None:
        """Newest *current* alias for a tier (optionally scoped to a provider).

        Returns ``None`` when the registry is empty or nothing matches, so the
        caller can fall back to its own config.
        """
        tier = (tier or "").lower()
        provider = (provider or "").lower()
        candidates = [
            m for m in self._models
            if self._tier_of(m).lower() == tier
            and str(m.get("status", "current")).lower() == "current"
            and (not provider or self._provider_of(m).lower() == provider)
        ]
        if not candidates:
            return None
        # Newest by release_date (ISO strings sort correctly); alias as tie-break.
        candidates.sort(key=lambda m: (str(m.get("release_date", "")), str(m.get("alias", ""))), reverse=True)
        return candidates[0].get("alias")

    def current_alias(self, family: str) -> str | None:
        """Newest current alias within a specific family."""
        cands = [m for m in self._models
                 if m.get("family") == family
                 and str(m.get("status", "current")).lower() == "current"]
        if not cands:
            return None
        cands.sort(key=lambda m: (str(m.get("release_date", "")), str(m.get("alias", ""))), reverse=True)
        return cands[0].get("alias")

    def status(self, alias: str) -> str:
        return str(self._by_alias.get(alias, {}).get("status", "unknown"))

    def is_deprecated(self, alias: str) -> bool:
        return self.status(alias).lower() == "deprecated"

    def family_of(self, alias: str) -> str | None:
        m = self._by_alias.get(alias)
        return m.get("family") if m else None

    def price(self, alias: str) -> dict | None:
        """Point-in-time unit price for a specific model (snapshot source)."""
        m = self._by_alias.get(alias)
        p = m.get("price") if m else None
        return dict(p) if isinstance(p, dict) else None

    def all_aliases(self) -> list[str]:
        return [m["alias"] for m in self._models]

    def all_current(self, tier: str | None = None) -> list[str]:
        out = []
        for m in self._models:
            if str(m.get("status", "current")).lower() != "current":
                continue
            if tier and self._tier_of(m).lower() != tier.lower():
                continue
            out.append(m["alias"])
        return out
