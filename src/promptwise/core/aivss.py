"""aivss -- AIVSS v0.5 agentic-dimensions threat-scoring rubric.

A documented, weighted rubric over four agentic risk dimensions (not a
learned model, not a black box): how much the agent acts autonomously,
how much tool/system access it has, whether it persists memory across
turns/sessions, and how far its effects can reach across other agents.
Each dimension gets a 0-100 raw sub-score from a caller (e.g.
core/anomaly_detector.py); this module only does the weighting and
aggregation into a single 0-100 composite `total`.

Shared between WP2 (behavioral anomaly detection) and WP3 (incident
response / forensics scoring) -- this module's public interface
(`score()`, `AIVSS_FACTORS` keys) is load-bearing for both; don't rename
factor keys without checking both call sites.

Weights below are this project's own documented interpretation of the
AIVSS v0.5 public draft's four agentic dimensions, not a vendor SDK --
stdlib only, no network, no ML.
"""
from __future__ import annotations

from dataclasses import dataclass, field

AIVSS_FACTORS: dict[str, float] = {
    "autonomy": 0.30,            # how independently the agent acted (no human in the loop)
    "tool_access": 0.30,         # breadth/power of tools the agent could reach
    "memory_persistence": 0.20,  # whether the behavior persists across turns/sessions
    "multi_agent_reach": 0.20,   # whether effects could propagate to other agents/actors
}


@dataclass
class AivssScore:
    total: float
    breakdown: dict[str, float] = field(default_factory=dict)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def score(factors: dict[str, float]) -> AivssScore:
    """Weight each 0-100 raw sub-score in `factors` by AIVSS_FACTORS and sum
    to a single 0-100 composite. Missing factor keys default to 0. Unknown
    keys in `factors` are ignored. Out-of-range values are clamped to
    [0, 100] before weighting."""
    breakdown: dict[str, float] = {}
    total = 0.0
    for name, weight in AIVSS_FACTORS.items():
        raw = _clamp(float(factors.get(name, 0.0)))
        contribution = raw * weight
        breakdown[name] = contribution
        total += contribution
    return AivssScore(total=total, breakdown=breakdown)
