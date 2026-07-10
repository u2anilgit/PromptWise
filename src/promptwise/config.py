from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR_HINTS = [
    Path("config"),
    Path("."),
]


@dataclass
class RateSpec:
    input_per_mtok: float = 3.0
    output_per_mtok: float = 15.0
    cache_write_per_mtok: float = 3.75
    cache_hit_per_mtok: float = 0.30
    batch_input_per_mtok: float = 1.5
    batch_output_per_mtok: float = 7.5


@dataclass
class ModelPricing:
    display_name: str = ""
    provider: str = "claude"
    tier: str = "balanced"
    context_window: int = 200000
    max_output: int = 8192
    rates: RateSpec = field(default_factory=RateSpec)


@dataclass
class ProviderConfig:
    display_name: str = ""
    aliases: list[str] = field(default_factory=list)
    fast: str = "claude-haiku-4-5-20251001"
    balanced: str = "claude-sonnet-4-6"
    powerful: str = "claude-opus-4-7"
    # Optional hard spend cap for this provider (e.g. daily). ``None`` (the
    # default) means unlimited -- opt-in, no behavior change unless configured.
    daily_cap_usd: float | None = None


@dataclass
class RoleConfig:
    display_name: str = ""
    prefix: str = ""
    description: str = ""


@dataclass
class TimeoutConfig:
    idle_threshold_minutes: int = 30
    warn_threshold_minutes: int = 20
    auto_action: str = "prompt_user"


@dataclass
class AutoCompactConfig:
    threshold_pct: float = 0.70
    threshold_tokens: int = 50000
    target_pct: float = 0.50


@dataclass
class PoliciesConfig:
    max_tokens_per_session: int = 500000
    budget_hard_stop_usd: float = 10.0
    daily_burn_warn_usd: float = 3.0
    team_budget_usd: float = 100.0


@dataclass
class SecurityConfig:
    checks: list[str] = field(default_factory=lambda: ["syntax", "secrets", "destructive", "supply_chain", "permissions", "pii", "injection", "compliance"])
    pii_detection: bool = True
    pii_action: str = "redact"
    injection_detection: bool = True
    injection_threshold: float = 0.7
    audit_log: bool = True


@dataclass
class SkillsConfig:
    directory: str = "skills/"
    auto_trigger: bool = True
    confidence_threshold: float = 0.6
    chain_mode: str = "sequential"
    max_chain_depth: int = 8
    output_validation: str = "strict"


@dataclass
class DashboardConfig:
    cli_enabled: bool = True
    web_enabled: bool = True
    web_port: int = 8765


@dataclass
class AnalyticsConfig:
    roi_tracking: bool = True
    per_developer: bool = True
    per_role: bool = True


@dataclass
class AppConfig:
    version: str = "1.0"
    default_model: str = "claude-sonnet-4-6"
    last_verified: str = "2025-10-01"
    models: dict[str, ModelPricing] = field(default_factory=dict)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    roles: dict[str, RoleConfig] = field(default_factory=dict)
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    auto_compact: AutoCompactConfig = field(default_factory=AutoCompactConfig)
    policies: PoliciesConfig = field(default_factory=PoliciesConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    analytics: AnalyticsConfig = field(default_factory=AnalyticsConfig)

    def get_model(self, name: str) -> ModelPricing:
        return self.models.get(name, ModelPricing())


def _find_config_dir(start: Path) -> Path:
    for hint in _CONFIG_DIR_HINTS:
        candidate = (start / hint).resolve()
        if candidate.exists():
            yaml_files = list(candidate.glob("*.yaml"))
            if yaml_files:
                return candidate
    return start.resolve()


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_config(config_dir: Path | str | None = None) -> AppConfig:
    cfg = AppConfig()

    if config_dir is None:
        config_dir = Path(__file__).resolve().parents[1]
    config_dir = Path(config_dir)
    config_dir = _find_config_dir(config_dir)

    raw = _load_yaml(config_dir / "promptwise.yaml")
    if not raw:
        raw = _load_yaml(config_dir / "promptwise.yaml")
    if not raw:
        raw = _load_yaml(config_dir / "promptwise.yaml")

    if not raw:
        return cfg

    cfg.version = str(raw.get("version", "1.0"))
    cfg.default_model = str(raw.get("default_model", cfg.default_model))
    cfg.last_verified = str(raw.get("last_verified", cfg.last_verified))

    models_data = raw.get("models", {}) or {}
    for name, m in models_data.items():
        rates = m.get("rates", {})
        cfg.models[name] = ModelPricing(
            display_name=m.get("display_name", name),
            provider=m.get("provider", "claude"),
            tier=m.get("tier", "balanced"),
            context_window=int(m.get("context_window", 200000)),
            max_output=int(m.get("max_output", 8192)),
            rates=RateSpec(**{k: float(v) for k, v in rates.items()}) if rates else RateSpec(),
        )

    providers_data = raw.get("providers", {}) or {}
    for name, p in providers_data.items():
        tiers = p.get("tiers", {})
        cap = p.get("daily_cap_usd")
        cfg.providers[name] = ProviderConfig(
            display_name=p.get("display_name", name),
            aliases=p.get("aliases", []),
            fast=tiers.get("fast", cfg.default_model),
            balanced=tiers.get("balanced", cfg.default_model),
            powerful=tiers.get("powerful", cfg.default_model),
            daily_cap_usd=float(cap) if cap is not None else None,
        )

    roles_data = raw.get("roles", {}) or {}
    for name, r in roles_data.items():
        cfg.roles[name] = RoleConfig(
            display_name=r.get("display_name", name),
            prefix=r.get("prefix", ""),
            description=r.get("description", ""),
        )

    timeout_raw = raw.get("timeout", {}) or {}
    cfg.timeout = TimeoutConfig(
        idle_threshold_minutes=int(timeout_raw.get("idle_threshold_minutes", 30)),
        warn_threshold_minutes=int(timeout_raw.get("warn_threshold_minutes", 20)),
        auto_action=str(timeout_raw.get("auto_action", "prompt_user")),
    )

    ac_raw = raw.get("auto_compact", {}) or {}
    cfg.auto_compact = AutoCompactConfig(
        threshold_pct=float(ac_raw.get("threshold_pct", 0.70)),
        threshold_tokens=int(ac_raw.get("threshold_tokens", 50000)),
        target_pct=float(ac_raw.get("target_pct", 0.50)),
    )

    pol_raw = raw.get("policies", {}) or {}
    cfg.policies = PoliciesConfig(
        max_tokens_per_session=int(pol_raw.get("max_tokens_per_session", 500000)),
        budget_hard_stop_usd=float(pol_raw.get("budget_hard_stop_usd", 10.0)),
        daily_burn_warn_usd=float(pol_raw.get("daily_burn_warn_usd", 3.0)),
        team_budget_usd=float(pol_raw.get("team_budget_usd", 100.0)),
    )

    sec_raw = raw.get("security", {}) or {}
    cfg.security = SecurityConfig(
        checks=sec_raw.get("checks", cfg.security.checks),
        pii_detection=bool(sec_raw.get("pii_detection", True)),
        pii_action=str(sec_raw.get("pii_action", "redact")),
        injection_detection=bool(sec_raw.get("injection_detection", True)),
        injection_threshold=float(sec_raw.get("injection_threshold", 0.7)),
        audit_log=bool(sec_raw.get("audit_log", True)),
    )

    skills_raw = raw.get("skills", {}) or {}
    cfg.skills = SkillsConfig(
        directory=str(skills_raw.get("directory", "skills/")),
        auto_trigger=bool(skills_raw.get("auto_trigger", True)),
        confidence_threshold=float(skills_raw.get("confidence_threshold", 0.6)),
        chain_mode=str(skills_raw.get("chain_mode", "sequential")),
        max_chain_depth=int(skills_raw.get("max_chain_depth", 8)),
        output_validation=str(skills_raw.get("output_validation", "strict")),
    )

    dash_raw = raw.get("dashboard", {}) or {}
    cfg.dashboard = DashboardConfig(
        cli_enabled=bool(dash_raw.get("cli_enabled", True)),
        web_enabled=bool(dash_raw.get("web_enabled", True)),
        web_port=int(dash_raw.get("web_port", 8765)),
    )

    analytics_raw = raw.get("analytics", {}) or {}
    cfg.analytics = AnalyticsConfig(
        roi_tracking=bool(analytics_raw.get("roi_tracking", True)),
        per_developer=bool(analytics_raw.get("per_developer", True)),
        per_role=bool(analytics_raw.get("per_role", True)),
    )

    return cfg
