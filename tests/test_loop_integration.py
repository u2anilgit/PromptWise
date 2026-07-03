"""End-to-end integration guard for the Phase 7+8 learning loop.

Proves the real modules wire together against a temp DB — no mocks of the units
under test: route_recorder -> OutcomeStore -> AdaptiveRouter.adapt (routing shift)
-> insights.compute_recommendations. This is the durable form of the Phase 8
dogfood verification.
"""
import os

import pytest

from promptwise.core.adaptive_router import OutcomeStore, AdaptiveRouter
from promptwise.core import route_recorder as rr
from promptwise.core import insights


CHEAP_CLASS = "coding/low"
HARD_CLASS = "coding/high"


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "loop.db")


def _seed(db, cls, tier, signal, n):
    rr.set_recorder(rr.RouteOutcomeRecorder(db_path=db))
    ids = []
    for _ in range(n):
        rid = rr.record_route_decision(cls, tier=tier, model_family="tierA", cost=0.001)
        rr.record_route_verdict(rid, signal)
        ids.append(rid)
    return ids


def test_recorder_writes_through_to_store(temp_db):
    _seed(temp_db, CHEAP_CLASS, "fast", "met", 8)
    stats = OutcomeStore(db_path=temp_db).stats(CHEAP_CLASS)
    assert stats["fast"]["met"] == 8
    assert stats["fast"]["not_met"] == 0


def test_adaptive_router_downgrades_on_cheap_success(temp_db):
    _seed(temp_db, CHEAP_CLASS, "fast", "met", 8)
    ar = AdaptiveRouter(store=OutcomeStore(db_path=temp_db))
    tier, reason = ar.adapt(CHEAP_CLASS, static_tier="powerful")
    assert tier == "fast"
    assert "cheaper tier" in reason


def test_adaptive_router_escalates_on_cheap_failure(temp_db):
    _seed(temp_db, HARD_CLASS, "fast", "not_met", 8)
    ar = AdaptiveRouter(store=OutcomeStore(db_path=temp_db))
    tier, reason = ar.adapt(HARD_CLASS, static_tier="fast")
    assert tier == "balanced"
    assert "escalated" in reason


def test_insights_recommends_escalation(temp_db):
    _seed(temp_db, HARD_CLASS, "fast", "not_met", 8)
    recs = insights.compute_recommendations(db_path=temp_db, window_days=30)
    routing = [r for r in recs if r["category"] == "routing"]
    assert routing, "expected a routing recommendation"
    assert any("escalate" in r["message"].lower() for r in routing)


def test_insights_fail_open_on_empty_db(tmp_path):
    recs = insights.compute_recommendations(db_path=str(tmp_path / "empty.db"), window_days=30)
    assert recs == []


def test_recording_flag_off_suppresses_writes(temp_db, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_ROUTE_RECORDING", "off")
    rr.set_recorder(rr.RouteOutcomeRecorder(db_path=temp_db))
    before = OutcomeStore(db_path=temp_db).stats("x/y")
    rr.record_route_decision("x/y", tier="fast")
    after = OutcomeStore(db_path=temp_db).stats("x/y")
    assert after == before


def teardown_module(_module):
    # Reset the process-global recorder so other tests get a clean default.
    rr.set_recorder(None)
    os.environ.pop("PROMPTWISE_ROUTE_RECORDING", None)
