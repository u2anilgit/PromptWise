"""Phase 8 WP8.1 — live-route outcome writer closes the learning loop.

Acceptance (docs/PHASE8_ROADMAP.md §8.1):
- A ``route_request`` writes ONE ``route_outcomes`` decision row with the right
  task_class / tier / model_family and a ``neutral`` signal, immediately.
- A later quality verdict for that route folds onto the row (met / not_met);
  absence of a verdict leaves it ``neutral``.
- Any recording error is swallowed and NEVER changes/breaks the route result.
- ``PROMPTWISE_ROUTE_RECORDING=off`` suppresses the write entirely.

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
from promptwise.core import route_recorder
from promptwise.core.route_recorder import RouteOutcomeRecorder
from promptwise.core.adaptive_router import OutcomeStore
from promptwise.core.model_registry import ModelRegistry
from promptwise.core.router import Router
from promptwise.plugins import CodeValidator

# ── a self-contained three-tier registry (no branded ids) ────────────────────
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
    """Minimal async memory stand-in (route_request only needs record_cost)."""
    async def record_cost(self, **kwargs):
        return None


def _ctx(registry):
    # SimpleNamespace only carries the three attrs route_request/validate_output/
    # run_quality_gate actually read; cast documents the deliberate shortfall
    # against the full 23-field ServerContext instead of building a real one.
    return typing.cast(server.ServerContext, SimpleNamespace(
        router=Router(registry=registry), memory=_Mem(), code_validator=CodeValidator()))


def _rows(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM route_outcomes")]
    finally:
        conn.close()


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    """Point the process recorder at a temp DB and default recording ON."""
    monkeypatch.setenv("PROMPTWISE_ROUTE_RECORDING", "on")
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_ROUTING", "off")  # exercise static tiers
    db_path = tmp_path / "outcomes.db"
    rec = RouteOutcomeRecorder(db_path=str(db_path))
    route_recorder.set_recorder(rec)
    try:
        yield SimpleNamespace(rec=rec, db_path=db_path)
    finally:
        route_recorder.set_recorder(None)


# ── the decision row is written immediately, neutral ─────────────────────────
def test_route_request_writes_neutral_decision_row(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "summarize this", "intent": "summarize", "stakes": "low", "provider": "testco"})))

    assert out["route_id"]  # returned so a verdict can correlate later
    rows = _rows(recorder.db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["task_class"] == "summarize/low"
    assert row["tier"] == "fast"
    assert row["model_family"] == "ff"
    assert row["quality_signal"] == "neutral"
    assert row["outcome_id"] == out["route_id"]


# ── a later verdict folds onto that row; absence stays neutral ───────────────
def test_verdict_sets_signal_met(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "write a function", "intent": "code", "stakes": "high", "provider": "testco"})))
    route_id = out["route_id"]

    # validate_output produces a validity verdict for that route -> met
    asyncio.run(server.call_tool(
        ctx, "validate_output", {"code": "x = 1\n", "language": "python", "route_id": route_id}))

    stats = OutcomeStore(str(recorder.db_path)).stats("code/high")
    assert stats["powerful"]["met"] == 1
    assert stats["powerful"]["neutral"] == 0


def test_quality_gate_verdict_sets_not_met(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "write a function", "intent": "code", "stakes": "high", "provider": "testco"})))
    route_id = out["route_id"]

    # a FAIL gate verdict (risk high, no waiver) -> not_met
    asyncio.run(server.call_tool(
        ctx, "run_quality_gate",
        {"story_id": "s1", "risk_score": 99, "findings": [{"severity": "high"}], "route_id": route_id}))

    stats = OutcomeStore(str(recorder.db_path)).stats("code/high")
    assert stats["powerful"]["not_met"] == 1


def test_no_verdict_leaves_signal_neutral(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    asyncio.run(server.call_tool(
        ctx, "route_request",
        {"text": "summarize this", "intent": "summarize", "stakes": "low", "provider": "testco"}))
    # no verdict ever arrives
    rows = _rows(recorder.db_path)
    assert len(rows) == 1
    assert rows[0]["quality_signal"] == "neutral"


def test_verdict_for_unknown_route_id_is_ignored(tmp_path, recorder):
    ctx = _ctx(_registry(tmp_path))
    # no exception, no row created/altered (an unrecorded verdict is a no-op)
    asyncio.run(server.call_tool(
        ctx, "validate_output", {"code": "x = 1\n", "route_id": "does-not-exist"}))
    assert OutcomeStore(str(recorder.db_path)).stats("code/high") == {}


# ── fail-open: a recording error never changes/breaks the route result ───────
def test_recording_error_does_not_break_route(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_ROUTE_RECORDING", "on")
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_ROUTING", "off")

    class BoomStore(OutcomeStore):
        def record_decision(self, *a, **k):
            raise RuntimeError("disk exploded")

    boom = RouteOutcomeRecorder(store=BoomStore(str(tmp_path / "x.db")))
    route_recorder.set_recorder(boom)
    try:
        ctx = _ctx(_registry(tmp_path))
        out = json.loads(asyncio.run(server.call_tool(
            ctx, "route_request",
            {"text": "write a function", "intent": "code", "stakes": "high", "provider": "testco"})))
        # route still succeeds, unchanged; only route_id is None
        assert out["recommended_model"] == "pow-cur"
        assert "error" not in out
        assert out["route_id"] is None
    finally:
        route_recorder.set_recorder(None)


# ── env flag off suppresses the write entirely ───────────────────────────────
def test_recording_disabled_suppresses_write(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_ROUTE_RECORDING", "off")
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_ROUTING", "off")
    db_path = tmp_path / "outcomes.db"
    route_recorder.set_recorder(RouteOutcomeRecorder(db_path=str(db_path)))
    try:
        ctx = _ctx(_registry(tmp_path))
        out = json.loads(asyncio.run(server.call_tool(
            ctx, "route_request",
            {"text": "summarize this", "intent": "summarize", "stakes": "low", "provider": "testco"})))
        assert out["route_id"] is None
        # store never wrote anything for this class
        assert OutcomeStore(str(db_path)).stats("summarize/low") == {}
    finally:
        route_recorder.set_recorder(None)
