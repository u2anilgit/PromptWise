from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class CoreConfig:
    max_context_tokens: int = 150000
    similarity_threshold: float = 0.65


@dataclass
class OrchestrationConfig:
    default_failure_strategy: str = "fallback"
    max_retries: int = 2
    fallback_model_sequence: list[str] = field(default_factory=lambda: ["sonnet", "haiku"])


@dataclass
class MemoryConfig:
    retention_weeks: int = 4
    auto_export_enabled: bool = True


@dataclass
class PluginsConfig:
    auto_load: bool = True
    enabled: list[str] = field(default_factory=list)


@dataclass
class CompressionConfig:
    enabled: bool = True
    auto_compress_threshold_usd_per_min: float = 0.01


@dataclass
class DashboardConfig:
    cli_enabled: bool = True
    web_enabled: bool = True
    web_port: int = 8765


@dataclass
class SecurityConfig:
    checks: list[str] = field(
        default_factory=lambda: ["syntax", "secrets", "destructive", "supply_chain", "permissions"]
    )


@dataclass
class PoliciesConfig:
    max_tokens_per_session: int = 500000
    budget_hard_stop_usd: float = 10.0
    daily_burn_warn_usd: float = 3.0
    team_budget_usd: float = 100.0


@dataclass
class AppConfigV2:
    version: str
    core: CoreConfig
    orchestration: OrchestrationConfig
    memory: MemoryConfig
    plugins: PluginsConfig
    compression: CompressionConfig
    dashboard: DashboardConfig
    security: SecurityConfig
    policies: PoliciesConfig


def load_config_v2(config_dir: Path) -> AppConfigV2:
    path = config_dir / "promptwise_v2.yaml"
    raw = yaml.safe_load(path.read_text())
    return AppConfigV2(
        version=raw.get("version", "2.0"),
        core=CoreConfig(**raw.get("core", {})),
        orchestration=OrchestrationConfig(**raw.get("orchestration", {})),
        memory=MemoryConfig(**raw.get("memory", {})),
        plugins=PluginsConfig(**raw.get("plugins", {})),
        compression=CompressionConfig(**raw.get("compression", {})),
        dashboard=DashboardConfig(**raw.get("dashboard", {})),
        security=SecurityConfig(**raw.get("security", {})),
        policies=PoliciesConfig(**raw.get("policies", {})),
    )
