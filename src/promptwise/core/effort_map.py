"""effort_map -- per-provider mapping from the internal effort label
(low/medium/high) to the concrete parameter a provider's API expects,
resolved the same way model_registry.resolve() resolves tier -> concrete
model id: config first, built-in defaults as the fallback.
"""
from __future__ import annotations

from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover - yaml always present in practice
    yaml = None  # type: ignore

_DEFAULTS = {
    "providers": {
        "claude": {
            "low": {"thinking_budget_tokens": 1024},
            "medium": {"thinking_budget_tokens": 4096},
            "high": {"thinking_budget_tokens": 16000},
        },
        "openai": {
            "low": {"reasoning_effort": "low"},
            "medium": {"reasoning_effort": "medium"},
            "high": {"reasoning_effort": "high"},
        },
    },
    "default_provider": "claude",
}


def _map_paths() -> list[Path]:
    return [
        Path("config") / "effort_map.yaml",
        Path(__file__).resolve().parents[3] / "config" / "effort_map.yaml",
    ]


def _load(path: str | Path | None) -> dict:
    candidates = [Path(path)] if path else _map_paths()
    if yaml is not None:
        for p in candidates:
            try:
                if not p.exists():
                    continue
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                if data.get("providers"):
                    return data
            except Exception:
                continue
    return _DEFAULTS


def resolve_effort_param(effort: str, provider: str = "claude",
                          path: str | Path | None = None) -> dict:
    """The provider-specific param dict for an internal effort label.
    Unknown provider falls back to ``default_provider``; unknown effort falls
    back to ``medium``. Never raises."""
    data = _load(path)
    providers = data.get("providers", {})
    table = providers.get(provider) or providers.get(data.get("default_provider", "claude")) or {}
    return dict(table.get(effort) or table.get("medium") or {})
