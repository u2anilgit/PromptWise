"""WP2 2b -- detect_anomalies: compare a window against a stored baseline,
score findings with the AIVSS rubric. Advisory only -- callers append
findings to the audit trail; this module never blocks.
"""
from promptwise.core.anomaly_detector import AnomalyFinding, SUSPICIOUS_BIGRAMS, detect_anomalies
from promptwise.core.behavior_baseline import BehaviorStats


def _baseline():
    return BehaviorStats(
        actor="alice", window_days=30,
        prompt_length_median=100.0, prompt_length_mad=10.0,
        tool_bigram_freq={"Read->Edit": 50, "Edit->Read": 40},
        model_tier_mix={"claude-haiku-4-5-20251001": 0.9, "claude-sonnet-4-6": 0.1},
        hourly_histogram={"10": 20, "11": 20, "14": 10}, distinct_files_touched=15)


def test_unchanged_actor_scores_low():
    baseline = _baseline()
    window = BehaviorStats(
        actor="alice", window_days=1,
        prompt_length_median=105.0, prompt_length_mad=12.0,
        tool_bigram_freq={"Read->Edit": 5, "Edit->Read": 4},
        model_tier_mix={"claude-haiku-4-5-20251001": 0.9, "claude-sonnet-4-6": 0.1},
        hourly_histogram={"10": 3, "11": 2}, distinct_files_touched=3)
    findings = detect_anomalies("alice", window=window, baseline=baseline)
    total = max((f.threat_score for f in findings), default=0.0)
    assert total < 30


def test_implanted_recon_sequence_scores_high():
    baseline = _baseline()
    recon_bigram = next(iter(SUSPICIOUS_BIGRAMS))
    window = BehaviorStats(
        actor="alice", window_days=1,
        prompt_length_median=5000.0, prompt_length_mad=10.0,   # far off-distribution
        tool_bigram_freq={recon_bigram: 20},                    # never-seen suspicious sequence
        model_tier_mix={"claude-opus-4-7": 1.0},                 # tier shift
        hourly_histogram={"3": 15}, distinct_files_touched=500)  # data-scope expansion
    findings = detect_anomalies("alice", window=window, baseline=baseline)
    total = max((f.threat_score for f in findings), default=0.0)
    assert total > 70


def test_off_distribution_volume_flagged_by_mad_threshold():
    baseline = _baseline()
    window = BehaviorStats(
        actor="alice", window_days=1,
        prompt_length_median=1000.0, prompt_length_mad=10.0,  # >3 MADs from baseline median 100
        tool_bigram_freq={}, model_tier_mix={}, hourly_histogram={}, distinct_files_touched=0)
    findings = detect_anomalies("alice", window=window, baseline=baseline)
    categories = {f.category for f in findings}
    assert "off_distribution_volume" in categories


def test_never_seen_bigram_flagged():
    baseline = _baseline()
    window = BehaviorStats(
        actor="alice", window_days=1,
        prompt_length_median=100.0, prompt_length_mad=10.0,
        tool_bigram_freq={"Bash->Bash": 5}, model_tier_mix={}, hourly_histogram={},
        distinct_files_touched=0)
    findings = detect_anomalies("alice", window=window, baseline=baseline)
    categories = {f.category for f in findings}
    assert "novel_tool_sequence" in categories


def test_data_scope_expansion_flagged():
    baseline = _baseline()  # distinct_files_touched=15
    window = BehaviorStats(
        actor="alice", window_days=1,
        prompt_length_median=100.0, prompt_length_mad=10.0,
        tool_bigram_freq={}, model_tier_mix={}, hourly_histogram={},
        distinct_files_touched=150)  # 10x baseline
    findings = detect_anomalies("alice", window=window, baseline=baseline)
    categories = {f.category for f in findings}
    assert "data_scope_expansion" in categories


def test_findings_have_aivss_breakdown_and_to_dict():
    baseline = _baseline()
    window = BehaviorStats(
        actor="alice", window_days=1, prompt_length_median=100.0, prompt_length_mad=10.0,
        tool_bigram_freq={"Bash->Bash": 5}, model_tier_mix={}, hourly_histogram={},
        distinct_files_touched=0)
    findings = detect_anomalies("alice", window=window, baseline=baseline)
    assert findings
    f = findings[0]
    assert isinstance(f, AnomalyFinding)
    d = f.to_dict()
    assert "threat_score" in d and "aivss_breakdown" in d and "evidence" in d
