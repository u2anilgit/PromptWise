"""WP2 2a -- per-actor statistical behavior baselines, pure stdlib stats
(median/MAD, frequency tables) over data already in cost_logs/audit JSONL.
No ML.
"""
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


def test_compute_baseline_live_fetch_path(monkeypatch):
    """Regression: compute_baseline() with no cost_logs/audit_records kwargs
    must actually work -- exercises MemoryManager(str(get_db_path())) and
    AuditLog().query(), the path that previously crashed with
    TypeError: __init__() missing 1 required positional argument: 'db_url'."""

    class _FakeMemoryManager:
        def __init__(self, db_url):
            self.db_url = db_url

        async def raw_cost_logs(self, since=None, project_id=None):
            return [_cost_log("Read", "m", "2026-08-01T10:00:00Z")]

    class _FakeAuditLog:
        def query(self, **kwargs):
            return [{"actor": "alice", "files_touched": ["a.py"]}]

    monkeypatch.setattr("promptwise.db.models.MemoryManager", _FakeMemoryManager)
    monkeypatch.setattr("promptwise.core.audit_log.AuditLog", _FakeAuditLog)

    stats = compute_baseline("alice")

    assert isinstance(stats, BehaviorStats)
    assert stats.actor == "alice"
    assert stats.model_tier_mix == {"m": 1.0}
    assert stats.distinct_files_touched == 1


def test_compute_baseline_live_fetch_applies_window_days(monkeypatch):
    """Regression: window_days must actually bound the live-fetch query --
    previously raw_cost_logs() was called with no `since` at all, so a
    'recent 1-day window' and a '30-day baseline' were byte-identical."""
    import calendar
    import time as _time

    captured = {}

    class _FakeMemoryManager:
        def __init__(self, db_url):
            self.db_url = db_url

        async def raw_cost_logs(self, since=None, project_id=None):
            captured["since"] = since
            return []

    class _FakeAuditLog:
        def query(self, **kwargs):
            return []

    monkeypatch.setattr("promptwise.db.models.MemoryManager", _FakeMemoryManager)
    monkeypatch.setattr("promptwise.core.audit_log.AuditLog", _FakeAuditLog)

    before = _time.time()
    compute_baseline("alice", window_days=7)
    after = _time.time()

    since = captured["since"]
    assert since is not None
    assert since.endswith("Z") and "T" in since  # "%Y-%m-%dT%H:%M:%SZ"
    since_epoch = calendar.timegm(_time.strptime(since, "%Y-%m-%dT%H:%M:%SZ"))
    expected_epoch = before - 7 * 86400
    # allow a small window for test execution time / clock skew
    assert abs(since_epoch - expected_epoch) < 5


def test_baseline_store_list_all_filters_by_actor(tmp_path):
    store = BaselineStore(tmp_path / "baselines.db")
    store.save("alice", "behavior", 30, {}, computed_at="2026-08-18T00:00:00Z")
    store.save("bob", "behavior", 30, {}, computed_at="2026-08-18T00:00:00Z")
    assert len(store.list_all()) == 2
    assert len(store.list_all(actor="alice")) == 1


# ── MCP tool handler ─────────────────────────────────────────────────────────
import asyncio
import json as _json
import typing

from promptwise.core.tool_registry import ServerContext
import promptwise.server  # noqa: F401 -- import server first so its own module-import
# order (not whatever order pytest happens to collect test files in) decides
# _TOOL_DEFS' registration order; importing handlers.detection directly
# without this can register its tools "early" if this test module is
# collected before anything else imports promptwise.server, which then
# reorders _TOOL_DEFS and breaks test_tool_registry_snapshot.py's golden
# ordering check in a full-suite run.
from promptwise.handlers.detection import _handle_baseline_behavior

_CTX = typing.cast(ServerContext, None)  # handlers in this file never read ctx


def test_baseline_behavior_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "promptwise.core.behavior_baseline._default_db", lambda: tmp_path / "wp2.db")
    out = _json.loads(asyncio.run(_handle_baseline_behavior(_CTX, {
        "actor": "alice", "window_days": 7,
        "cost_logs": [{"tool": "Read", "model": "m", "ts": "2026-08-01T10:00:00Z",
                        "input_tokens": 100.0}],
        "audit_records": []})))
    assert out["actor"] == "alice"
    assert out["window_days"] == 7
    assert out["saved"] is True
