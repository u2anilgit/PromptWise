"""Shared type definitions for PromptWise."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TokenCount:
    """Token count with method metadata."""

    value: int
    method: str
    model: str


@dataclass(frozen=True)
class RewriteResult:
    """Result of prompt rewriting."""

    original: str
    rewritten: str
    role: str
    raw_tokens: int
    rewritten_tokens: int
    saving_pct: float
    model_used_for_count: str
    warning: str | None = None


@dataclass(frozen=True)
class OptimizeResult:
    """Result of context optimization."""

    original: str
    optimized: str
    raw_tokens: int
    optimized_tokens: int
    saving_pct: float
    chunks_dropped: int
    budget: int
    cache_candidates: list[str]
    model_used_for_count: str


@dataclass(frozen=True)
class RouteResult:
    """Result of model routing."""

    recommended_model: str
    recommended_display: str
    reason: str
    intent_detected: str
    stakes_detected: str
    tool_chain_depth: int
    input_tokens: int
    estimated_input_cost_usd: float
    estimated_output_cost_usd: float
    context_window_pct: float
    context_window_warning: str | None
    task_budget_recommended: int
    peak_hour_warning: str | None
    cost_floor_breached: bool
    alternatives: list[dict]
    batch_recommended: bool = False


@dataclass(frozen=True)
class CacheBreakpoint:
    """Cache recommendation for a message."""

    message_index: int
    ttl: str
    rationale: str
    tokens: int


@dataclass(frozen=True)
class CachePlanResult:
    """Result of cache planning."""

    breakpoints: list[CacheBreakpoint]
    cost_without_cache_usd: float
    cost_with_cache_usd: float
    savings_pct: float
    notes: list[str]
    expected_reuse_count: int


@dataclass(frozen=True)
class BatchResult:
    """Result of prompt batching."""

    batched_prompt: str
    tasks: list[str]
    individual_tokens: int
    batched_tokens: int
    reload_reduction_tokens: int
    saving_pct: float
    model_used_for_count: str


@dataclass(frozen=True)
class SummaryResult:
    """Result of thread summarization."""

    summary: str
    reset_prompt: str
    original_tokens: int
    summary_tokens: int
    saving_pct: float
    sentences_kept: int
    sentences_dropped: int
    model_used_for_count: str


@dataclass(frozen=True)
class StatsSnapshot:
    """Snapshot of session statistics."""

    total_calls: int
    total_input_tokens: int
    total_cached_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    cost_by_model: dict[str, float]
    calls_by_tool: dict[str, int]
    avg_saving_pct: float
    cache_hit_rate: float
    calls_by_model: dict[str, int] = field(default_factory=dict)
    tokens_by_model: dict[str, int] = field(default_factory=dict)
    total_duration_ms: int = 0
    since: str | None = None


@dataclass(frozen=True)
class ReloadResult:
    """Result of configuration reload."""

    reloaded: bool
    config_summary: dict
    error: str | None = None


@dataclass(frozen=True)
class SessionPingResult:
    """Result of session ping."""

    session_id: str
    started_ts: str
    last_ping_ts: str
    is_new: bool


@dataclass(frozen=True)
class TimeoutCheckResult:
    """Result of session timeout check."""

    session_id: str
    status: str  # "active" | "warn" | "expired"
    idle_minutes: float
    recommended_action: str  # "continue" | "prompt_user" | "summarize_thread"
    message: str


@dataclass(frozen=True)
class ClearHistoryResult:
    """Result of history clearing."""

    deleted_count: int
    older_than_days: int


@dataclass(frozen=True)
class TurnInput:
    """A single conversation turn."""

    role: str
    content: str


@dataclass(frozen=True)
class CompactResult:
    """Result of auto-compaction."""

    status: str                 # "ok" | "compacted"
    original_tokens: int
    compacted_tokens: int
    turns_kept: int
    turns_dropped: int
    saving_pct: float
    compacted_turns: list       # [{role, content}] in original chronological order
    threshold_used: str         # "pct" | "tokens" | "none"
    model_used_for_count: str
