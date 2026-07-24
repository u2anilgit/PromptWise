"""technique_recorder -- live-technique outcome writer, wiring
technique_adapter into a production caller. Structurally mirrors
test_effort_recording.py but over the prompting-technique axis:

- ``suggest_technique`` writes ONE ``technique_outcomes`` decision row with
  the right task_class/technique and a ``neutral`` signal, immediately, and
  returns ``technique_id`` to correlate a later verdict.
- A later quality verdict for that technique decision folds onto the row.
- Any recording error is swallowed and NEVER changes/breaks the response.
- ``PROMPTWISE_TECHNIQUE_RECORDING=off`` suppresses the write entirely.

The store is always pointed at a temp DB (never the real ~/.promptwise DB).
"""
import asyncio
import json
import sqlite3
import typing
from types import SimpleNamespace

import pytest

import promptwise.server as server
from promptwise.core import technique_recorder
from promptwise.core.technique_recorder import TechniqueOutcomeRecorder
from promptwise.core.technique_adapter import TechniqueOutcomeStore
from promptwise.core.router import Router
from promptwise.plugins import CodeValidator


def _ctx():
    return typing.cast(server.ServerContext, SimpleNamespace(
        router=Router(), code_validator=CodeValidator()))


def _rows(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM technique_outcomes")]
    finally:
        conn.close()


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_TECHNIQUE_RECORDING", "on")
    db_path = tmp_path / "outcomes.db"
    rec = TechniqueOutcomeRecorder(db_path=str(db_path))
    technique_recorder.set_recorder(rec)
    try:
        yield SimpleNamespace(rec=rec, db_path=db_path)
    finally:
        technique_recorder.set_recorder(None)


def test_suggest_technique_writes_neutral_decision_row(recorder):
    ctx = _ctx()
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "suggest_technique", {"prompt": "please give me an example of a decorator"})))

    assert out["technique_id"]
    assert out["technique"] == "Few-Shot"
    rows = _rows(recorder.db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["technique"] == out["technique"]
    assert row["quality_signal"] == "neutral"
    assert row["outcome_id"] == out["technique_id"]


def test_verdict_sets_technique_signal_met(recorder):
    ctx = _ctx()
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "suggest_technique", {"prompt": "please give me an example of a decorator"})))
    technique_id = out["technique_id"]

    asyncio.run(server.call_tool(
        ctx, "validate_output", {"code": "x = 1\n", "language": "python", "technique_id": technique_id}))

    task_class = ctx.router.detect_intent("please give me an example of a decorator")
    stats = TechniqueOutcomeStore(str(recorder.db_path)).stats(task_class)
    assert stats[out["technique"]]["met"] == 1
    assert stats[out["technique"]]["neutral"] == 0


def test_quality_gate_verdict_sets_technique_signal_not_met(recorder):
    ctx = _ctx()
    out = json.loads(asyncio.run(server.call_tool(
        ctx, "suggest_technique", {"prompt": "please give me an example of a decorator"})))
    technique_id = out["technique_id"]

    asyncio.run(server.call_tool(
        ctx, "run_quality_gate",
        {"story_id": "s1", "risk_score": 99, "findings": [{"severity": "high"}], "technique_id": technique_id}))

    task_class = ctx.router.detect_intent("please give me an example of a decorator")
    stats = TechniqueOutcomeStore(str(recorder.db_path)).stats(task_class)
    assert stats[out["technique"]]["not_met"] == 1


def test_technique_verdict_for_unknown_id_is_ignored(recorder):
    ctx = _ctx()
    asyncio.run(server.call_tool(
        ctx, "validate_output", {"code": "x = 1\n", "technique_id": "does-not-exist"}))
    # No decision was ever recorded (nothing called suggest_technique in this
    # test) -- an unknown id must be a no-op, not create/mutate anything.
    assert TechniqueOutcomeStore(str(recorder.db_path)).stats("code") == {}


def test_technique_recording_error_does_not_break_response(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_TECHNIQUE_RECORDING", "on")

    class BoomStore(TechniqueOutcomeStore):
        def record_decision(self, *a, **k):
            raise RuntimeError("disk exploded")

    boom = TechniqueOutcomeRecorder(store=BoomStore(str(tmp_path / "x.db")))
    technique_recorder.set_recorder(boom)
    try:
        ctx = _ctx()
        out = json.loads(asyncio.run(server.call_tool(
            ctx, "suggest_technique", {"prompt": "please give me an example of a decorator"})))
        assert out["technique"] == "Few-Shot"
        assert "error" not in out
        assert out["technique_id"] is None
    finally:
        technique_recorder.set_recorder(None)


def test_technique_recording_disabled_suppresses_write(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_TECHNIQUE_RECORDING", "off")
    db_path = tmp_path / "outcomes.db"
    technique_recorder.set_recorder(TechniqueOutcomeRecorder(db_path=str(db_path)))
    try:
        ctx = _ctx()
        out = json.loads(asyncio.run(server.call_tool(
            ctx, "suggest_technique", {"prompt": "please give me an example of a decorator"})))
        assert out["technique_id"] is None
        assert TechniqueOutcomeStore(str(db_path)).stats("code") == {}
    finally:
        technique_recorder.set_recorder(None)
