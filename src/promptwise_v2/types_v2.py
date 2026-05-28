from dataclasses import dataclass, field


@dataclass(frozen=True)
class SecurityResult:
    passed: bool
    checks_run: list[str]
    violations: list[dict]
    risk_score: float
    blocked: bool = False
    details: str = ""


@dataclass(frozen=True)
class ContextFile:
    path: str
    relevance_score: float
    selection_tier: str
    tokens: int


@dataclass(frozen=True)
class OrchestratorResult:
    task_id: str
    status: str
    steps_total: int
    steps_done: int
    strategy_used: str
    output: str
    cost_usd: float
    duration_ms: int
    error: str | None = None


@dataclass(frozen=True)
class CompressionResult:
    original: str
    compressed: str
    tokens_saved: int
    saving_pct: float
    rules_applied: list[str]


@dataclass(frozen=True)
class MemoryEntry:
    entry_id: str
    session_id: str
    ts: str
    tool: str
    summary: str
    cost_usd: float
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RoleProfile:
    role: str
    confidence: float
    keywords_matched: list[str]
    recommended_model_tier: str
    context_hint: str


@dataclass(frozen=True)
class PluginEvent:
    plugin_name: str
    trigger: str
    action_taken: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BudgetStatus:
    used_usd: float
    limit_usd: float
    pct_used: float
    daily_burn_usd: float
    projected_monthly_usd: float
    alert_level: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: list[dict]
    confidence: float
    checks_run: list[str]
    suggested_fix: str = ""


@dataclass(frozen=True)
class ROISnapshot:
    session_id: str
    total_cost_usd: float
    tokens_saved: int
    estimated_time_saved_min: float
    roi_ratio: float
    productivity_score: float
