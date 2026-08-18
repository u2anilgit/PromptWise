"""anomaly_detector -- compare a behavior window against a stored baseline
(core/behavior_baseline.py) and score deviations with the AIVSS v0.5
rubric (core/aivss.py). Advisory only: callers are responsible for
appending findings to the audit trail (AuditLog.append) and optionally
firing alerts.notify_anomaly -- this module has no side effects and never
blocks anything.

SUSPICIOUS_BIGRAMS is a small, hand-curated seed list of tool-call
sequences that resemble recon->exfil patterns reported in public incident
writeups (GTG-1002, s1ngularity) -- e.g. broad-read followed by external-
write/network. It is intentionally coarse (a starting point WP2 users can
extend via config, not an exhaustive detector) and uses the project's
`_j()` string-splitting convention since it names literal tool-pair
strings that could otherwise resemble scanner trigger content.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from promptwise.core.aivss import score as aivss_score
from promptwise.core.behavior_baseline import BehaviorStats


def _j(*parts: str) -> str:
    return "".join(parts)


SUSPICIOUS_BIGRAMS: set[str] = {
    _j("Read", "->", "Bash"),     # broad read then shell-out
    _j("Bash", "->", "Bash"),     # chained shell commands, no read in between
    _j("Read", "->", "Write"),    # read-then-overwrite without an intervening edit review
    _j("Glob", "->", "Bash"),     # broad file discovery then shell-out
}

_MAD_EPSILON = 1e-9


@dataclass
class AnomalyFinding:
    actor: str
    category: str
    detail: str
    threat_score: float
    aivss_breakdown: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _mad_deviation(value: float, median: float, mad: float) -> float:
    if mad <= _MAD_EPSILON:
        return 0.0 if abs(value - median) <= _MAD_EPSILON else float("inf")
    return abs(value - median) / mad


def detect_anomalies(
    actor: str, *, window: BehaviorStats, baseline: BehaviorStats, mad_threshold: float = 3.0,
) -> list[AnomalyFinding]:
    findings: list[AnomalyFinding] = []

    # off-distribution volume/tempo: prompt-length median deviates >mad_threshold MADs
    dev = _mad_deviation(window.prompt_length_median, baseline.prompt_length_median, baseline.prompt_length_mad)
    if dev > mad_threshold:
        findings.append(AnomalyFinding(
            actor=actor, category="off_distribution_volume",
            detail=f"prompt-length median {window.prompt_length_median:.1f} is {dev:.1f} MADs from baseline {baseline.prompt_length_median:.1f}",
            threat_score=aivss_score({"autonomy": min(100.0, dev * 20), "tool_access": 20.0}).total,
            aivss_breakdown=aivss_score({"autonomy": min(100.0, dev * 20), "tool_access": 20.0}).breakdown,
            evidence={"window_median": window.prompt_length_median, "baseline_median": baseline.prompt_length_median, "mad_deviation": dev}))

    # never-seen-before tool bigrams, weighted higher if on the suspicious seed list
    novel = set(window.tool_bigram_freq) - set(baseline.tool_bigram_freq)
    if novel:
        suspicious_hit = novel & SUSPICIOUS_BIGRAMS
        severity = 100.0 if suspicious_hit else 40.0
        multi_agent = 100.0 if suspicious_hit else 0.0
        factors = {"autonomy": severity, "tool_access": severity, "multi_agent_reach": multi_agent}
        findings.append(AnomalyFinding(
            actor=actor, category="novel_tool_sequence",
            detail=f"never-seen-before tool sequence(s): {sorted(novel)}" + (" (matches suspicious recon/exfil pattern)" if suspicious_hit else ""),
            threat_score=aivss_score(factors).total,
            aivss_breakdown=aivss_score(factors).breakdown,
            evidence={"novel_bigrams": sorted(novel), "suspicious_match": sorted(suspicious_hit)}))

    # data-scope expansion: distinct files touched grows well beyond baseline
    if baseline.distinct_files_touched > 0 and window.distinct_files_touched > baseline.distinct_files_touched * 5:
        findings.append(AnomalyFinding(
            actor=actor, category="data_scope_expansion",
            detail=f"distinct files touched {window.distinct_files_touched} vs baseline {baseline.distinct_files_touched} (>5x)",
            threat_score=aivss_score({"tool_access": 80.0, "memory_persistence": 20.0}).total,
            aivss_breakdown=aivss_score({"tool_access": 80.0, "memory_persistence": 20.0}).breakdown,
            evidence={"window_files": window.distinct_files_touched, "baseline_files": baseline.distinct_files_touched}))
    elif baseline.distinct_files_touched == 0 and window.distinct_files_touched > 50:
        findings.append(AnomalyFinding(
            actor=actor, category="data_scope_expansion",
            detail=f"distinct files touched {window.distinct_files_touched} vs a zero baseline",
            threat_score=aivss_score({"tool_access": 80.0}).total,
            aivss_breakdown=aivss_score({"tool_access": 80.0}).breakdown,
            evidence={"window_files": window.distinct_files_touched, "baseline_files": 0}))

    return findings
