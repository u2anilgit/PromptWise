"""WP2 2a -- per-actor statistical behavior baselines, pure stdlib stats
(median/MAD, frequency tables) over data already in cost_logs/audit JSONL.
No ML.
"""
from promptwise.core.audit_log import AuditLog
from promptwise.core.behavior_baseline import BaselineStore, BehaviorStats, compute_baseline


def _cost_log(tool, model, ts, cost=0.01):
    return {"tool": tool, "model": model, "ts": ts, "cost_usd": cost,
            "input_tokens": 100.0, "output_tokens": 50.0, "session_id": "s1"}


def test_compute_baseline_from_supplied_cost_logs():
    logs = [
        _cost_log("Read", "claude-haiku-4-5-20251001", "2026-08-01T10:00:00Z"),
        _cost_log("Edit", "claude-sonnet-4-6", "2026-08-01T10:05:00Z"),
        _cost_log("Read", "claude-haiku-4-5-20251001", "2026-08-01T11:00:00Z"),
    ]
    stats = compute_baseline("alice", window_days=30, cost_logs=logs, audit_records=[])
    assert isinstance(stats, BehaviorStats)
    assert stats.actor == "alice"
    assert stats.window_days == 30
    assert stats.model_tier_mix["claude-haiku-4-5-20251001"] == 2 / 3
    assert stats.model_tier_mix["claude-sonnet-4-6"] == 1 / 3


def test_compute_baseline_tool_bigram_frequencies():
    logs = [
        _cost_log("Read", "m", "2026-08-01T10:00:00Z"),
        _cost_log("Edit", "m", "2026-08-01T10:01:00Z"),
        _cost_log("Read", "m", "2026-08-01T10:02:00Z"),
        _cost_log("Edit", "m", "2026-08-01T10:03:00Z"),
    ]
    stats = compute_baseline("alice", cost_logs=logs, audit_records=[])
    # Bigrams: Read->Edit, Edit->Read, Read->Edit
    assert stats.tool_bigram_freq["Read->Edit"] == 2
    assert stats.tool_bigram_freq["Edit->Read"] == 1


def test_compute_baseline_hourly_histogram():
    logs = [
        _cost_log("Read", "m", "2026-08-01T10:00:00Z"),
        _cost_log("Read", "m", "2026-08-01T10:30:00Z"),
        _cost_log("Read", "m", "2026-08-01T14:00:00Z"),
    ]
    stats = compute_baseline("alice", cost_logs=logs, audit_records=[])
    assert stats.hourly_histogram["10"] == 2
    assert stats.hourly_histogram["14"] == 1


def test_compute_baseline_empty_logs_returns_zeroed_stats():
    stats = compute_baseline("alice", cost_logs=[], audit_records=[])
    assert stats.prompt_length_median == 0.0
    assert stats.prompt_length_mad == 0.0
    assert stats.tool_bigram_freq == {}
    assert stats.model_tier_mix == {}
    assert stats.hourly_histogram == {}
    assert stats.distinct_files_touched == 0


def test_compute_baseline_distinct_files_from_audit_records():
    audit = [
        {"actor": "alice", "files_touched": ["a.py", "b.py"]},
        {"actor": "alice", "files_touched": ["b.py", "c.py"]},
        {"actor": "bob", "files_touched": ["z.py"]},
    ]
    stats = compute_baseline("alice", cost_logs=[], audit_records=audit)
    assert stats.distinct_files_touched == 3  # a.py, b.py, c.py


def test_baseline_store_round_trip(tmp_path):
    store = BaselineStore(tmp_path / "baselines.db")
    stats = compute_baseline("alice", cost_logs=[], audit_records=[])
    store.save("alice", "behavior", 30, stats.to_dict(), computed_at="2026-08-18T00:00:00Z")
    loaded = store.load("alice", "behavior", 30)
    assert loaded is not None
    assert loaded["stats_json"]["actor"] == "alice"
    assert loaded["computed_at"] == "2026-08-18T00:00:00Z"


def test_baseline_store_load_unknown_returns_none(tmp_path):
    store = BaselineStore(tmp_path / "baselines.db")
    assert store.load("nobody", "behavior", 30) is None


def test_baseline_store_list_all_filters_by_actor(tmp_path):
    store = BaselineStore(tmp_path / "baselines.db")
    store.save("alice", "behavior", 30, {}, computed_at="2026-08-18T00:00:00Z")
    store.save("bob", "behavior", 30, {}, computed_at="2026-08-18T00:00:00Z")
    assert len(store.list_all()) == 2
    assert len(store.list_all(actor="alice")) == 1
