from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class RouteResult:
    recommended_model: str
    reason: str
    intent_detected: str
    stakes_detected: str
    estimated_input_cost_usd: float
    context_window_pct: float
    task_budget_recommended: float | None = None
    peak_hour_warning: str | None = None
    cost_floor_breached: bool = False
    alternatives: list[str] = field(default_factory=list)
    batch_recommended: bool = False
    batch_recommendation_note: str | None = None
    provider_capped: bool = False


@dataclass(frozen=True)
class RewriteResult:
    rewritten: str
    saving_pct: float
    warning: str | None = None
    raw_tokens: int = 0


@dataclass(frozen=True)
class OptimizeResult:
    optimized: str
    saving_pct: float
    chunks_dropped: int = 0
    raw_tokens: int = 0


@dataclass(frozen=True)
class CachePlanResult:
    breakpoints: list[dict]
    savings_pct: float


@dataclass(frozen=True)
class BatchResult:
    batched_prompt: str
    saving_pct: float
    individual_tokens: int = 0


@dataclass(frozen=True)
class SummarizeResult:
    summary: str
    reset_prompt: str | None = None
    saving_pct: float = 0.0
    original_tokens: int = 0
    summary_tokens: int = 0


@dataclass(frozen=True)
class CompactResult:
    status: str
    original_tokens: int
    compacted_tokens: int
    turns_kept: int
    turns_dropped: int
    saving_pct: float
    compacted_turns: list[dict] = field(default_factory=list)
    threshold_used: str = ""


@dataclass(frozen=True)
class SecurityResult:
    passed: bool
    checks_run: list[str]
    violations: list[dict]
    risk_score: float
    blocked: bool = False
    details: str = ""


@dataclass(frozen=True)
class CompressionResult:
    original: str
    compressed: str
    tokens_saved: int
    saving_pct: float
    rules_applied: list[str]


@dataclass(frozen=True)
class RoleProfile:
    role: str
    confidence: float
    keywords_matched: list[str]
    recommended_model_tier: str
    context_hint: str


@dataclass(frozen=True)
class RoleDetectionResult:
    primary_role: str
    confidence: float
    secondary_roles: list[tuple[str, float]]
    keywords_matched: list[str]
    rationale: str


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
class MemoryEntry:
    entry_id: str
    session_id: str
    ts: str
    tool: str
    summary: str
    cost_usd: float = 0.0
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QualityResult:
    score: float
    passed: bool
    signals: list[str]


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: list[dict]
    confidence: float
    checks_run: list[str]
    suggested_fix: str = ""


@dataclass(frozen=True)
class BudgetStatus:
    used_usd: float
    limit_usd: float
    pct_used: float
    daily_burn_usd: float
    projected_monthly_usd: float
    alert_level: str
    project_id: str | None = None
    cost_breakdown: dict[str, float] | None = None


@dataclass(frozen=True)
class ROISnapshot:
    session_id: str
    total_cost_usd: float
    tokens_saved: int
    estimated_time_saved_min: float
    roi_ratio: float
    productivity_score: float

    def __post_init__(self):
        if self.total_cost_usd < 0:
            raise ValueError(f"total_cost_usd must be >= 0, got {self.total_cost_usd}")
        if self.tokens_saved < 0:
            raise ValueError(f"tokens_saved must be >= 0, got {self.tokens_saved}")
        if not 0.0 <= self.productivity_score <= 1.0:
            raise ValueError(f"productivity_score must be 0.0-1.0, got {self.productivity_score}")


@dataclass(frozen=True)
class PluginEvent:
    plugin_name: str
    trigger: str
    action_taken: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ToolRequest:
    tool_name: str
    params: dict
    session_id: str
    context: Optional[dict] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.tool_name:
            raise ValueError("tool_name is required")
        if not self.session_id:
            raise ValueError("session_id is required")
        if not isinstance(self.params, dict):
            raise ValueError("params must be a dict")


@dataclass
class ToolResponse:
    result: dict
    error: Optional[str] = None
    execution_ms: int = 0
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def success(self) -> bool:
        return self.error is None

    def __str__(self) -> str:
        if self.error:
            return f"ToolResponse(error={self.error}, duration={self.execution_ms}ms)"
        return f"ToolResponse(result_keys={list(self.result.keys())}, duration={self.execution_ms}ms)"


@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str]
    depends_on: list[str]
    output_schema: dict | None
    roles: list[str]
    model_tier: str
    system_prompt: str
    raw_content: str
