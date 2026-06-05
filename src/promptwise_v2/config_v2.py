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
class IntelligenceMemoryConfig:
    cross_session: bool = True
    org_vault_enabled: bool = True
    retention_tiers: dict[str, str] = field(default_factory=lambda: {
        "working": "session",
        "episodic": "4_weeks",
        "semantic": "permanent"
    })


@dataclass
class IntelligenceAutocompleteConfig:
    enabled: bool = True
    latency_target_ms: int = 150
    confidence_threshold: float = 0.7


@dataclass
class IntelligenceProactiveConfig:
    enabled: bool = True
    complexity_threshold: int = 10
    test_gap_watcher: bool = True


@dataclass
class IntelligenceAutonomousLoopsConfig:
    enabled: bool = True
    max_iterations: int = 5
    checkpoint_mode: str = "manual"


@dataclass
class IntelligenceConfig:
    memory: IntelligenceMemoryConfig = field(default_factory=IntelligenceMemoryConfig)
    autocomplete: IntelligenceAutocompleteConfig = field(default_factory=IntelligenceAutocompleteConfig)
    proactive: IntelligenceProactiveConfig = field(default_factory=IntelligenceProactiveConfig)
    autonomous_loops: IntelligenceAutonomousLoopsConfig = field(default_factory=IntelligenceAutonomousLoopsConfig)


@dataclass
class RolesConfig:
    current: str = "Dev"
    available: list[str] = field(default_factory=lambda: ["Dev", "IT", "PM", "EM", "SM", "NTM"])
    compliance_profiles: dict[str, str] = field(default_factory=dict)


@dataclass
class ComplianceFrameworksConfig:
    banking: list[str] = field(default_factory=list)
    healthcare: list[str] = field(default_factory=list)
    legal: list[str] = field(default_factory=list)
    all: list[str] = field(default_factory=list)


@dataclass
class ComplianceConfig:
    pii_detection: bool = True
    pii_action: str = "redact"
    injection_detection: bool = True
    injection_threshold: float = 0.7
    owasp_check: str = "post_generation"
    audit_log: bool = True
    frameworks: ComplianceFrameworksConfig = field(default_factory=ComplianceFrameworksConfig)


@dataclass
class SkillsConfig:
    directory: str = "skills/"
    auto_trigger: bool = True
    confidence_threshold: float = 0.6
    auto_load_on_start: bool = True
    chain_mode: str = "sequential"
    max_chain_depth: int = 8
    output_validation: str = "strict"


@dataclass
class AnalyticsConfig:
    roi_tracking: bool = True
    per_developer: bool = True
    per_role: bool = True
    slack_digest: str = "weekly"
    pdf_report: str = "monthly"


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
    intelligence: IntelligenceConfig
    roles: RolesConfig
    compliance: ComplianceConfig
    skills: SkillsConfig
    analytics: AnalyticsConfig


def load_config_v2(config_dir: Path) -> AppConfigV2:
    path = (config_dir / "promptwise_v2.yaml").resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raise ValueError(f"Config file is empty: {path}")

    raw_intel = raw.get("intelligence", {})
    raw_intel_mem = raw_intel.get("memory", {})
    raw_intel_auto = raw_intel.get("autocomplete", {})
    raw_intel_pro = raw_intel.get("proactive", {})
    raw_intel_loops = raw_intel.get("autonomous_loops", {})

    intel = IntelligenceConfig(
        memory=IntelligenceMemoryConfig(**{k: v for k, v in raw_intel_mem.items() if v is not None}),
        autocomplete=IntelligenceAutocompleteConfig(**{k: v for k, v in raw_intel_auto.items() if v is not None}),
        proactive=IntelligenceProactiveConfig(**{k: v for k, v in raw_intel_pro.items() if v is not None}),
        autonomous_loops=IntelligenceAutonomousLoopsConfig(**{k: v for k, v in raw_intel_loops.items() if v is not None})
    )

    raw_roles = raw.get("roles", {})
    roles = RolesConfig(**{k: v for k, v in raw_roles.items() if v is not None})

    raw_comp = raw.get("compliance", {})
    raw_frameworks = raw_comp.get("frameworks", {})
    frameworks = ComplianceFrameworksConfig(**{k: v for k, v in raw_frameworks.items() if v is not None})
    comp_args = {k: v for k, v in raw_comp.items() if k != "frameworks" and v is not None}
    compliance = ComplianceConfig(frameworks=frameworks, **comp_args)

    raw_skills = raw.get("skills", {})
    skills = SkillsConfig(**{k: v for k, v in raw_skills.items() if v is not None})

    raw_analytics = raw.get("analytics", {})
    analytics = AnalyticsConfig(**{k: v for k, v in raw_analytics.items() if v is not None})

    return AppConfigV2(
        version=str(raw.get("version", "1.0")),
        core=CoreConfig(**{k: v for k, v in raw.get("core", {}).items() if v is not None}),
        orchestration=OrchestrationConfig(**{k: v for k, v in raw.get("orchestration", {}).items() if v is not None}),
        memory=MemoryConfig(**{k: v for k, v in raw.get("memory", {}).items() if v is not None}),
        plugins=PluginsConfig(**{k: v for k, v in raw.get("plugins", {}).items() if v is not None}),
        compression=CompressionConfig(**{k: v for k, v in raw.get("compression", {}).items() if v is not None}),
        dashboard=DashboardConfig(**{k: v for k, v in raw.get("dashboard", {}).items() if v is not None}),
        security=SecurityConfig(**{k: v for k, v in raw.get("security", {}).items() if v is not None}),
        policies=PoliciesConfig(**{k: v for k, v in raw.get("policies", {}).items() if v is not None}),
        intelligence=intel,
        roles=roles,
        compliance=compliance,
        skills=skills,
        analytics=analytics
    )
