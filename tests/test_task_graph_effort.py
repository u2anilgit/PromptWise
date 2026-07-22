"""plan_waves must surface a per-task effort label alongside the existing
id/depends_on/file fields -- effort attaches to orchestrated task graphs the
same way it now attaches to a single route_request call (Task 9)."""
from promptwise.core.task_graph import plan_waves


def test_plan_waves_surfaces_task_effort_defaulting_to_medium():
    tasks = [
        {"id": "a", "depends_on": [], "effort": "high"},
        {"id": "b", "depends_on": ["a"]},
    ]
    plan = plan_waves(tasks)
    assert plan["task_effort"] == {"a": "high", "b": "medium"}


def test_plan_waves_task_effort_covers_every_task_including_cycles():
    tasks = [
        {"id": "x", "depends_on": ["y"], "effort": "low"},
        {"id": "y", "depends_on": ["x"], "effort": "low"},
    ]
    plan = plan_waves(tasks)
    assert plan["has_cycle"] is True
    assert plan["task_effort"] == {"x": "low", "y": "low"}
