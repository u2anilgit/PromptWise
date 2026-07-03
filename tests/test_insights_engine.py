"""Phase 8 WP8.2 — insights recommendation engine.

Acceptance (docs/PHASE8_ROADMAP.md §8.2):
- A class meeting the bar cheaply -> a "downgrade" rec with the right class/tier
  and a non-negative estimated saving.
- A class failing at a cheap tier -> an "escalate" rec.
- Cost rows -> a top-cost-driver rec.
- Empty/thin DB -> [] (no crash; fail-open).
- Recs are ranked (impact x confidence, desc) and min-sample gated.
- The original ``compute_insights`` correction view still works.

Every test uses a temp DB path — never the real ~/.promptwise DB. Routing recs
reuse the SAME 7.1 thresholds (min_samples=5, meet_bar=0.7, fail_bar=0.4) so a
recommendation can never contradict the adaptive router.
"""
import sqlite3
from datetime import datetime, timezone

from promptwise.core.adaptive_router import OutcomeStore
from promptwise.core.insights import compute_insights, compute_recommendations
from promptwise.core.learning_store import LearningStore

REQUIRED_KEYS = {"id", "category", "message", "evidence", "estimated_impact",
                 "confidence", "score"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_cost_logs(db_path, rows):
    """rows: list of (tool, model, cost_usd). Seeds the cost_logs table (current ts)."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cost_logs (
                   log_id TEXT PRIMARY KEY, session_id TEXT, ts TEXT,
                   tool TEXT, model TEXT, input_tokens REAL, output_tokens REAL,
                   cost_usd REAL, saving_pct REAL, lines REAL)""")
        ts = _now_iso()
        for i, (tool, model, cost) in enumerate(rows):
            conn.execute(
                "INSERT INTO cost_logs (log_id, session_id, ts, tool, model, "
                "input_tokens, output_tokens, cost_usd, saving_pct, lines) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (f"c{i}", "s", ts, tool, model, 0, 0, float(cost), 0, 0))
        conn.commit()
    finally:
        conn.close()


# ── routing: downgrade ────────────────────────────────────────────────────────
def test_downgrade_rec_for_class_meeting_bar_cheaply(tmp_path):
    db = tmp_path / "pw.db"
    store = OutcomeStore(db)
    for _ in range(8):
        store.record("summarize", "fast", "met", cost=0.001)
    for _ in range(6):
        store.record("summarize", "balanced", "met", cost=0.02)

    recs = compute_recommendations(db_path=str(db))
    downgrades = [r for r in recs if r["category"] == "routing" and "downgrade" in r["id"]]
    assert downgrades, "expected a downgrade recommendation"
    r = downgrades[0]
    assert r["evidence"]["task_class"] == "summarize"
    assert r["evidence"]["target_tier"] == "fast"
    assert r["estimated_impact"] >= 0.0        # non-negative saving
    assert REQUIRED_KEYS <= set(r)


# ── routing: escalate ─────────────────────────────────────────────────────────
def test_escalate_rec_for_class_failing_cheaply(tmp_path):
    db = tmp_path / "pw.db"
    store = OutcomeStore(db)
    for _ in range(6):
        store.record("refactor", "fast", "not_met", cost=0.001)
    for _ in range(2):
        store.record("refactor", "fast", "met", cost=0.001)

    recs = compute_recommendations(db_path=str(db))
    escalations = [r for r in recs if r["category"] == "routing" and "escalate" in r["id"]]
    assert escalations, "expected an escalate recommendation"
    r = escalations[0]
    assert r["evidence"]["task_class"] == "refactor"
    assert r["evidence"]["from_tier"] == "fast"
    assert r["evidence"]["to_tier"] == "balanced"


# ── cost: top driver ──────────────────────────────────────────────────────────
def test_top_cost_driver_rec(tmp_path):
    db = tmp_path / "pw.db"
    OutcomeStore(db)  # ensure the DB file / dir exist
    rows = [("route_request", "family-powerful", 0.10)] * 8 + \
           [("route_request", "family-fast", 0.05)] * 2
    _seed_cost_logs(db, rows)

    recs = compute_recommendations(db_path=str(db))
    cost = [r for r in recs if r["category"] == "cost"]
    assert cost, "expected a cost-driver recommendation"
    assert any("family-powerful" in r["message"] or
               "family-powerful" in str(r["evidence"]) for r in cost)
    assert all(r["estimated_impact"] >= 0 for r in cost)


# ── fail-open: empty / thin DB ────────────────────────────────────────────────
def test_empty_db_returns_no_recs_no_crash(tmp_path):
    db = tmp_path / "empty.db"
    recs = compute_recommendations(db_path=str(db))
    assert recs == []


def test_thin_routing_below_min_samples_is_gated(tmp_path):
    db = tmp_path / "pw.db"
    store = OutcomeStore(db)
    # only 2 samples for this class — below min_samples (5)
    for _ in range(2):
        store.record("tiny", "balanced", "met", cost=0.01)
    recs = compute_recommendations(db_path=str(db))
    assert not [r for r in recs if r["category"] == "routing"
                and r["evidence"].get("task_class") == "tiny"]


# ── ranking + shape ───────────────────────────────────────────────────────────
def test_recs_are_ranked_and_well_formed(tmp_path):
    db = tmp_path / "pw.db"
    store = OutcomeStore(db)
    for _ in range(8):
        store.record("summarize", "fast", "met", cost=0.001)
    for _ in range(6):
        store.record("summarize", "balanced", "met", cost=0.05)
    _seed_cost_logs(db, [("route_request", "family-powerful", 0.10)] * 8 +
                        [("route_request", "family-fast", 0.05)] * 2)

    recs = compute_recommendations(db_path=str(db))
    assert len(recs) >= 2
    for r in recs:
        assert REQUIRED_KEYS <= set(r)
        assert 0.0 <= r["confidence"] <= 1.0
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True), "recs must be ranked by score desc"


# ── the original correction view still works ──────────────────────────────────
def test_compute_insights_still_works(tmp_path):
    db = tmp_path / "pw.db"
    ls = LearningStore(db)
    ls.capture(category="style", mistake="tabs not spaces", correction="use spaces",
               project="alpha")
    ls.capture(category="style", mistake="tabs not spaces", correction="use spaces",
               project="alpha")
    out = compute_insights(db)
    assert out["total_learnings"] == 2
    assert out["top_category"] == "style"
    assert out["by_project"].get("alpha") == 2
