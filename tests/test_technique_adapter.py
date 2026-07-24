"""Prompting-technique outcome-learning -- see
docs/superpowers/specs/2026-07-24-technique-outcome-learning-design.md.
"""
from promptwise.core.technique_adapter import TechniqueAdapter, TechniqueOutcomeStore


def test_thin_history_keeps_static_pick(tmp_path):
    store = TechniqueOutcomeStore(tmp_path / "tech.db")
    adapter = TechniqueAdapter(store=store, min_samples=5)
    technique, reason = adapter.adapt("code", "CRAFT")
    assert technique == "CRAFT"
    assert reason == ""


def test_strong_alternative_evidence_switches(tmp_path):
    store = TechniqueOutcomeStore(tmp_path / "tech.db")
    for _ in range(8):
        store.record("code", "Chain-of-Thought", quality_signal="met")
    adapter = TechniqueAdapter(store=store, min_samples=5, meet_bar=0.7, margin=0.1)
    technique, reason = adapter.adapt("code", "CRAFT")
    assert technique == "Chain-of-Thought"
    assert "switched from 'CRAFT'" in reason


def test_weak_alternative_evidence_keeps_static_pick(tmp_path):
    store = TechniqueOutcomeStore(tmp_path / "tech.db")
    for _ in range(3):
        store.record("code", "Chain-of-Thought", quality_signal="met")
    for _ in range(3):
        store.record("code", "Chain-of-Thought", quality_signal="not_met")
    adapter = TechniqueAdapter(store=store, min_samples=5, meet_bar=0.7)
    technique, reason = adapter.adapt("code", "CRAFT")
    assert technique == "CRAFT"
    assert reason == ""


def test_static_pick_with_strong_history_is_not_switched_away_from_itself(tmp_path):
    store = TechniqueOutcomeStore(tmp_path / "tech.db")
    for _ in range(8):
        store.record("code", "CRAFT", quality_signal="met")
    adapter = TechniqueAdapter(store=store, min_samples=5, meet_bar=0.7)
    technique, reason = adapter.adapt("code", "CRAFT")
    assert technique == "CRAFT"
    assert reason == ""


def test_alternative_must_beat_static_by_margin_not_merely_tie(tmp_path):
    store = TechniqueOutcomeStore(tmp_path / "tech.db")
    for _ in range(8):
        store.record("code", "CRAFT", quality_signal="met")
    for _ in range(8):
        store.record("code", "Chain-of-Thought", quality_signal="met")
    adapter = TechniqueAdapter(store=store, min_samples=5, meet_bar=0.7, margin=0.1)
    technique, reason = adapter.adapt("code", "CRAFT")
    # Both have ~the same posterior mean (near-identical met rates) -- no
    # switch without a clear margin of improvement.
    assert technique == "CRAFT"


def test_different_task_classes_are_independent(tmp_path):
    store = TechniqueOutcomeStore(tmp_path / "tech.db")
    for _ in range(8):
        store.record("code", "Chain-of-Thought", quality_signal="met")
    adapter = TechniqueAdapter(store=store, min_samples=5)
    technique, _ = adapter.adapt("summarize", "CRAFT")
    assert technique == "CRAFT"


def test_record_decision_and_update_signal_round_trip(tmp_path):
    store = TechniqueOutcomeStore(tmp_path / "tech.db")
    outcome_id = store.record_decision("code", "CRAFT")
    stats_before = store.stats("code")
    assert stats_before["CRAFT"]["neutral"] == 1
    store.update_signal(outcome_id, True)
    stats_after = store.stats("code")
    assert stats_after["CRAFT"]["met"] == 1
    assert stats_after["CRAFT"]["neutral"] == 0
