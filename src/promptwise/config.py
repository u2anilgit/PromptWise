"""Configuration loading and validation for PromptWise."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class ConfigError(Exception):
    """Raised when configuration validation fails."""

    pass


class RateSpec(BaseModel):
    """Pricing rates for a model."""

    input_per_mtok: float = Field(..., gt=0)
    output_per_mtok: float = Field(..., gt=0)
    cache_write_5m_per_mtok: float = Field(..., gt=0)
    cache_write_1h_per_mtok: float = Field(..., gt=0)
    cache_hit_per_mtok: float = Field(..., gt=0)
    batch_input_per_mtok: float = Field(..., gt=0)
    batch_output_per_mtok: float = Field(..., gt=0)


class TokenizerSpec(BaseModel):
    """Tokenizer configuration for a model."""

    family: str
    inflation_vs_baseline: float = Field(..., gt=0)


class ModelPricing(BaseModel):
    """Pricing information for a single model."""

    display_name: str
    provider: str
    tier: str
    context_window: int = Field(..., gt=0)
    max_output: int = Field(..., gt=0)
    rates: RateSpec
    tokenizer: TokenizerSpec
    notes: str = ""


class ProviderTierConfig(BaseModel):
    """Tier mapping for a provider."""

    fast: str
    balanced: str
    powerful: str


class ProviderConfig(BaseModel):
    """Provider configuration."""

    display_name: str
    aliases: list[str] = Field(default_factory=list)
    tiers: ProviderTierConfig
    switch_command: str = ""
    peak_hours_utc: list[int] = Field(default_factory=list)
    feature_warnings: list[str] = Field(default_factory=list)

    @field_validator("peak_hours_utc")
    @classmethod
    def validate_hours(cls, v):
        for hour in v:
            if not 0 <= hour <= 23:
                raise ValueError(f"Hour must be 0-23, got {hour}")
        return v

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, v):
        for alias in v:
            if not alias.islower() or " " in alias:
                raise ValueError(f"Alias must be lowercase without spaces: {alias}")
        return v


class RoleSpec(BaseModel):
    """Role configuration."""

    display_name: str
    prefix: str = ""
    description: str = ""


@dataclass(frozen=True)
class TimeoutConfig:
    """Session timeout configuration."""

    idle_threshold_minutes: int = 30
    warn_threshold_minutes: int = 20
    auto_action: str = "prompt_user"  # "prompt_user" or "summarize_and_exit"


@dataclass(frozen=True)
class AutoCompactConfig:
    """Auto-compact threshold configuration."""

    threshold_pct: float = 0.70     # fire when > 70% of model's context window
    threshold_tokens: int = 50000   # fire when > 50k tokens (whichever fires first)
    target_pct: float = 0.50        # compact down to 50% of context window


class PricingYAML(BaseModel):
    """Top-level pricing YAML structure."""

    schema_version: int
    last_verified: str
    default_model: str
    models: dict[str, ModelPricing]


class ProvidersYAML(BaseModel):
    """Top-level providers YAML structure."""

    schema_version: int
    providers: dict[str, ProviderConfig]


class RolesYAML(BaseModel):
    """Top-level roles YAML structure."""

    schema_version: int
    preamble_phrases: list[str] = Field(default_factory=list)
    filler_words: list[str] = Field(default_factory=list)
    roles: dict[str, RoleSpec]


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file, raise ConfigError on failure."""
    if not path.exists():
        raise ConfigError(f"{path.name} not found")
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise ConfigError(f"Failed to parse {path.name}: {e}")


def _validate_provider_tiers(
    providers_config: ProvidersYAML, pricing_config: PricingYAML
) -> None:
    """Validate that provider tiers reference models in pricing.yaml."""
    pricing_models = set(pricing_config.models.keys())
    for provider_name, provider in providers_config.providers.items():
        for tier_name, model_id in provider.tiers.model_dump().items():
            if model_id not in pricing_models:
                raise ConfigError(
                    f"providers.{provider_name}.tiers.{tier_name} references '{model_id}' "
                    f"which is not in pricing.yaml models"
                )


@dataclass(frozen=True)
class AppConfig:
    """Application configuration."""

    pricing: PricingYAML
    providers: ProvidersYAML
    roles: RolesYAML
    default_model: str
    last_verified: str
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    auto_compact: AutoCompactConfig = field(default_factory=AutoCompactConfig)


def load_config(config_dir: Path | str = ".") -> AppConfig:
    """Load and validate PromptWise configuration from YAML files.

    Args:
        config_dir: Directory containing pricing.yaml, providers.yaml, roles.yaml

    Returns:
        AppConfig with validated configuration

    Raises:
        ConfigError: On validation failures
    """
    config_dir = Path(config_dir)

    try:
        pricing_data = _load_yaml(config_dir / "pricing.yaml")
        pricing_config = PricingYAML(**pricing_data)

        providers_data = _load_yaml(config_dir / "providers.yaml")
        providers_config = ProvidersYAML(**providers_data)

        roles_data = _load_yaml(config_dir / "roles.yaml")
        roles_config = RolesYAML(**roles_data)

        _validate_provider_tiers(providers_config, pricing_config)

        # Optional timeout + auto_compact config from promptwise.yaml
        timeout = TimeoutConfig()
        auto_compact = AutoCompactConfig()
        promptwise_yaml = config_dir / "promptwise.yaml"
        if promptwise_yaml.exists():
            try:
                tw_data = _load_yaml(promptwise_yaml)
                if "timeout" in tw_data:
                    t = tw_data["timeout"]
                    timeout = TimeoutConfig(
                        idle_threshold_minutes=int(t.get("idle_threshold_minutes", 30)),
                        warn_threshold_minutes=int(t.get("warn_threshold_minutes", 20)),
                        auto_action=str(t.get("auto_action", "prompt_user")),
                    )
                if "auto_compact" in tw_data:
                    ac = tw_data["auto_compact"]
                    auto_compact = AutoCompactConfig(
                        threshold_pct=float(ac.get("threshold_pct", 0.70)),
                        threshold_tokens=int(ac.get("threshold_tokens", 50000)),
                        target_pct=float(ac.get("target_pct", 0.50)),
                    )
            except Exception:
                pass  # malformed promptwise.yaml — fall back to defaults

        return AppConfig(
            pricing=pricing_config,
            providers=providers_config,
            roles=roles_config,
            default_model=pricing_config.default_model,
            last_verified=pricing_config.last_verified,
            timeout=timeout,
            auto_compact=auto_compact,
        )
    except ConfigError:
        raise
    except Exception as e:
        raise ConfigError(f"Configuration loading failed: {e}")
