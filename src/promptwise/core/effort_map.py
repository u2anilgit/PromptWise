"""effort_map -- per-provider mapping from the internal effort label
(low/medium/high) to the concrete parameter a provider's API expects,
resolved the same way model_registry.resolve() resolves tier -> concrete
model id: config first, built-in defaults as the fallback.
"""
from __future__ import annotations

from pathlib import Path

from promptwise.asset_paths import resolve_asset

try:
    import yaml
except Exception:  # pragma: no cover - yaml always present in practice
    yaml = None  # type: ignore

_DEFAULTS = {
    "providers": {
        "claude": {
            "supported": ["none", "low", "medium", "high", "xhigh"],
            "none": {"thinking_budget_tokens": 0},
            "low": {"thinking_budget_tokens": 1024},
            "medium": {"thinking_budget_tokens": 4096},
            "high": {"thinking_budget_tokens": 16000},
            "xhigh": {"thinking_budget_tokens": 32000},
        },
        "openai": {
            "supported": ["none", "low", "medium", "high"],
            "none": {"reasoning_effort": "minimal"},
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
        resolve_asset("config/effort_map.yaml"),
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


def nearest_supported(effort: str, supported) -> str:
    """Clamp an effort rung to the nearest one a provider actually accepts.

    A provider with no ``none`` rung should get its cheapest real rung, not a
    dropped parameter: sending no effort parameter at all is a different -- and
    usually more expensive -- request than the one the caller asked for. Ties
    resolve downward, so a clamp never silently costs more than requested.
    """
    from promptwise.core.effort_router import EFFORT_ORDER
    supported = [s for s in (supported or []) if s in EFFORT_ORDER]
    if not supported:
        return effort
    if effort in supported:
        return effort
    try:
        want = EFFORT_ORDER.index(effort)
    except ValueError:
        # Not a rung at all -- pass it through untouched so the caller's own
        # "unknown effort falls back to medium" rule still applies. Clamping a
        # typo to the cheapest rung would silently downgrade the request.
        return effort
    return min(supported, key=lambda s: (abs(EFFORT_ORDER.index(s) - want),
                                         EFFORT_ORDER.index(s)))


def resolve_effort_param(effort: str, provider: str = "claude",
                          path: str | Path | None = None) -> dict:
    """The provider-specific param dict for an internal effort label.

    Unknown provider falls back to ``default_provider``. An effort the provider
    does not offer is clamped to its nearest supported rung rather than dropped.
    Never raises.
    """
    data = _load(path)
    providers = data.get("providers", {})
    table = providers.get(provider) or providers.get(data.get("default_provider", "claude")) or {}
    if not isinstance(table, dict):
        return {}
    effort = nearest_supported(effort, table.get("supported"))
    return dict(table.get(effort) or table.get("medium") or {})
