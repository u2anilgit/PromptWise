"""Regression tests for handlers/detection.py MCP tool handlers -- found by
an end-to-end tool smoke test that calls every MCP tool through the real
async `call_tool` dispatch path.

Bug 1: baseline_behavior's async handler used to let compute_baseline()'s
own live-fetch path run asyncio.run() from inside an already-running event
loop, crashing every real call that omits cost_logs. The handler must
pre-fetch cost_logs itself with `await` instead.

Bug 2: detect_anomalies's handler constructed BehaviorStats(**window) with
no defaulting, so a caller-supplied `window` dict missing `actor`/
`window_days` (both required, no-default dataclass fields) raised a raw
TypeError instead of defaulting sensibly.
"""
import json

import pytest

import promptwise.handlers.detection as detection_handlers


class _FakeCtx:
    pass


def _cost_log(tool, model, ts, cost=0.01):
    return {"tool": tool, "model": model, "ts": ts, "cost_usd": cost,
            "input_tokens": 100.0, "output_tokens": 50.0, "session_id": "s1"}


@pytest.mark.asyncio
async def test_baseline_behavior_handler_live_fetch_from_running_loop(tmp_path, monkeypatch):
    """Regression: previously crashed with
    RuntimeError: asyncio.run() cannot be called from a running event loop
    -- pytest.mark.asyncio gives this test an actual running loop, exactly
    like the real MCP server's call_tool dispatch."""

    class _FakeMemoryManager:
        def __init__(self, db_url):
            self.db_url = db_url

        async def raw_cost_logs(self, since=None, project_id=None):
            return [_cost_log("Read", "m", "2026-08-01T10:00:00Z")]

    monkeypatch.setattr("promptwise.db.models.MemoryManager", _FakeMemoryManager)
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "pw.db")
    monkeypatch.setattr(
        "promptwise.core.behavior_baseline.BaselineStore",
        lambda *a, **kw: type("S", (), {"save": lambda self, *a, **kw: None})())

    out = await detection_handlers._handle_baseline_behavior(_FakeCtx(), {"actor": "alice"})

    result = json.loads(out)
    assert "error" not in result
    assert result["actor"] == "alice"
    assert result["saved"] is True


@pytest.mark.asyncio
async def test_detect_anomalies_handler_partial_window_dict(tmp_path, monkeypatch):
    """Regression: previously crashed with
    TypeError: __init__() missing 2 required positional arguments:
    'actor' and 'window_days' when `window` omitted them."""
    monkeypatch.setattr(
        "promptwise.core.behavior_baseline.BaselineStore",
        lambda *a, **kw: type("S", (), {"load": lambda self, *a, **kw: None})())

    out = await detection_handlers._handle_detect_anomalies(_FakeCtx(), {
        "actor": "alice", "window": {"tool_bigram_freq": {}}})

    result = json.loads(out)
    assert "error" not in result
    assert result["actor"] == "alice"
    assert "findings" in result
