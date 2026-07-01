"""Phase 6 WP4 — safe-parallelization planner (waves, cycles, shared files, cap)."""
from promptwise.core.task_graph import plan_waves, summarize_plan


def test_independent_tasks_run_in_one_wave():
    tasks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    p = plan_waves(tasks)
    assert p["wave_count"] == 1
    assert set(p["waves"][0]) == {"a", "b", "c"}
    assert not p["has_cycle"]


def test_dependencies_produce_ordered_waves():
    tasks = [
        {"id": "a"},
        {"id": "b", "depends_on": ["a"]},
        {"id": "c", "depends_on": ["a"]},
        {"id": "d", "depends_on": ["b", "c"]},
    ]
    p = plan_waves(tasks)
    assert p["waves"][0] == ["a"]
    assert set(p["waves"][1]) == {"b", "c"}
    assert p["waves"][2] == ["d"]


def test_cycle_is_detected_not_misordered():
    tasks = [
        {"id": "a", "depends_on": ["b"]},
        {"id": "b", "depends_on": ["a"]},
    ]
    p = plan_waves(tasks)
    assert p["has_cycle"]
    assert p["cycle"] == ["a", "b"]
    assert p["waves"] == []


def test_shared_file_writers_are_serialized():
    tasks = [
        {"id": "a", "file": "shared.py"},
        {"id": "b", "file": "shared.py"},
        {"id": "c", "file": "other.py"},
    ]
    p = plan_waves(tasks)
    # a and b touch the same file -> never in the same wave
    for w in p["waves"]:
        assert not ({"a", "b"} <= set(w))
    assert "b" in p["serialized"]
    assert p["wave_count"] == 2


def test_fan_out_cap_limits_wave_width():
    tasks = [{"id": f"t{i}"} for i in range(20)]
    p = plan_waves(tasks, fan_out_cap=5)
    assert p["max_parallel"] == 5
    assert p["capped"] is True
    # all tasks still scheduled across waves
    scheduled = [i for w in p["waves"] for i in w]
    assert len(scheduled) == 20


def test_unknown_and_self_deps_ignored():
    tasks = [{"id": "a", "depends_on": ["ghost", "a"]}, {"id": "b", "depends_on": ["a"]}]
    p = plan_waves(tasks)
    assert p["waves"][0] == ["a"]
    assert p["waves"][1] == ["b"]
    assert not p["has_cycle"]


def test_summary_readable():
    assert "wave" in summarize_plan(plan_waves([{"id": "a"}]))
    assert "cycle" in summarize_plan(plan_waves([{"id": "a", "depends_on": ["b"]},
                                                 {"id": "b", "depends_on": ["a"]}]))
