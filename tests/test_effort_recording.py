"""effort_recorder -- live-effort outcome writer, wiring effort_adapter/
effort_map into a production caller. Structurally mirrors
test_route_recording.py but over the effort axis (independent of model tier):

- ``route_request`` writes ONE ``effort_outcomes`` decision row with the
  right task_class/effort and a ``neutral`` signal, immediately, and returns
  both ``effort_id`` (to correlate a later verdict) and ``effort_param`` (the
  concrete provider param resolved from effort_map.yaml).
- A later quality verdict for that effort decision folds onto the row
  (met/not_met); absence of a verdict leaves it ``neutral``.
- Any recording error is swallowed and NEVER changes/breaks the route result.
- ``PROMPTWISE_EFFORT_RECORDING=off`` suppresses the write entirely.

The store is always pointed at a temp DB (never the real ~/.promptwise DB).
"""
import asyncio
import json
import sqlite3
import textwrap
import typing
from types import SimpleNamespace

import pytest

import promptwise.server as server
from promptwise.core import effort_recorder
from promptwise.core.effort_recorder import EffortOutcomeRecorder
from promptwise.core.effort_adapter import EffortOutcomeStore
from promptwise.core.model_registry import ModelRegistry
from promptwise.core.router import Router
from promptwise.plugins import CodeValidator

REG = textwrap.dedent("""
schema_version: 1
families:
  ff: { provider: testco, tier: fast }
  bf: { provider: testco, tier: balanced }
  pf: { provider: testco, tier: powerful }
models:
  - { alias: fast-cur, family: ff, status: current, release_date: "2026-01-01", price: {input_per_mtok: 1.0, output_per_mtok: 2.0} }
  - { alias: bal-cur, family: bf, status: current, release_date: "2026-01-01", price: {input_per_mtok: 3.0, output_per_mtok: 6.0} }
  - { alias: pow-cur, family: pf, status: current, release_date: "2026-01-01", price: {input_per_mtok: 10.0, output_per_mtok: 20.0} }
""")


def _registry(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(REG, encoding="utf-8")
    return ModelRegistry(p)


class _Mem:
    async def record_cost(self, **kwargs):
        return None


def _ctx(registry):
    return typing.cast(server.ServerContext, SimpleNamespace(
        router=Router(registry=registry), memory=_Mem(), code_validator=CodeValidator()))


def _rows(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM effort_outcomes")]
    finally:
        conn.close()


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    """Point the process effort recorder at a temp DB, recording ON, adaptive
    effort OFF (exercise the static heuristic so task_class/effort are
    deterministic)."""
    monkeypatch.setenv("PROMPTWISE_EFFORT_RECORDING", "on")
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_EFFORT", "off")
    db_path = tmp_path / "outcomes.db"
    rec = EffortOutcomeRecorder(db_path=str(db_path))
    effort_recorder.set_recorder(rec)
    try:
        yield SimpleNamespace(rec=rec, db_path=db_path)
    finally:
        effort_recorder.set_recorder(None)


def test_route_request_writes_neutral_effort_decision_row(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "write a function", "intent": "code", "stakes": "high", "provider": "testco"})))

    assert out["effort_id"]  # returned so a verdict can correlate later
    assert out["effort"] in ("low", "medium", "high")
    assert isinstance(out["effort_param"], dict)
    rows = _rows(recorder.db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["task_class"] == "code/high"
    assert row["effort"] == out["effort"]
    assert row["quality_signal"] == "neutral"
    assert row["outcome_id"] == out["effort_id"]


def test_effort_param_resolves_for_claude_provider(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "write a function", "intent": "code", "stakes": "high", "provider": "claude"})))
    # effort_map.yaml's claude table always has a concrete key for every effort
    assert out["effort_param"]
    assert any(k in out["effort_param"] for k in ("thinking_budget_tokens", "reasoning_effort"))


def test_effort_id_and_route_id_are_independent(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "write a function", "intent": "code", "stakes": "high", "provider": "testco"})))
    assert out["effort_id"] != out["route_id"]


def test_verdict_sets_effort_signal_met(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "write a function", "intent": "code", "stakes": "high", "provider": "testco"})))
    effort_id = out["effort_id"]

    asyncio.run(server.call_tool(
        ctx, "validate_output", {"code": "x = 1\n", "language": "python", "effort_id": effort_id}))

    stats = EffortOutcomeStore(str(recorder.db_path)).stats("code/high")
    assert stats[out["effort"]]["met"] == 1
    assert stats[out["effort"]]["neutral"] == 0


def test_quality_gate_verdict_sets_effort_signal_not_met(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "write a function", "intent": "code", "stakes": "high", "provider": "testco"})))
    effort_id = out["effort_id"]

    asyncio.run(server.call_tool(
        ctx, "run_quality_gate",
        {"story_id": "s1", "risk_score": 99, "findings": [{"severity": "high"}], "effort_id": effort_id}))

    stats = EffortOutcomeStore(str(recorder.db_path)).stats("code/high")
    assert stats[out["effort"]]["not_met"] == 1


def test_no_effort_verdict_leaves_signal_neutral(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "summarize this", "intent": "summarize", "stakes": "low", "provider": "testco"}))
    rows = _rows(recorder.db_path)
    assert len(rows) == 1
    assert rows[0]["quality_signal"] == "neutral"


def test_effort_verdict_for_unknown_id_is_ignored(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    asyncio.run(server.call_tool(
        ctx, "validate_output", {"code": "x = 1\n", "effort_id": "does-not-exist"}))
    assert EffortOutcomeStore(str(recorder.db_path)).stats("code/high") == {}


def test_effort_recording_error_does_not_break_route(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_EFFORT_RECORDING", "on")
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_EFFORT", "off")

    class BoomStore(EffortOutcomeStore):
        def record_decision(self, *a, **k):
            raise RuntimeError("disk exploded")

    boom = EffortOutcomeRecorder(store=BoomStore(str(tmp_path / "x.db")))
    effort_recorder.set_recorder(boom)
    try:
        ctx = _ctx(_registry(tmp_path))
        out = json.loads(asyncio.run(server.call_tool(
            ctx, "route_request",
            {"text": "write a function", "intent": "code", "stakes": "high", "provider": "testco"})))
        assert out["recommended_model"] == "pow-cur"
        assert "error" not in out
        assert out["effort_id"] is None
    finally:
        effort_recorder.set_recorder(None)


def test_effort_recording_disabled_suppresses_write(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_EFFORT_RECORDING", "off")
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_EFFORT", "off")
    db_path = tmp_path / "outcomes.db"
    effort_recorder.set_recorder(EffortOutcomeRecorder(db_path=str(db_path)))
    try:
        ctx = _ctx(_registry(tmp_path))
        out = json.loads(asyncio.run(server.call_tool(
            ctx, "route_request",
            {"text": "summarize this", "intent": "summarize", "stakes": "low", "provider": "testco"})))
        assert out["effort_id"] is None
        assert EffortOutcomeStore(str(db_path)).stats("summarize/low") == {}
    finally:
        effort_recorder.set_recorder(None)
