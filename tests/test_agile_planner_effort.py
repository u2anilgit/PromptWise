"""AgileStep must carry a reasoning-effort level alongside model_tier --
planning steps default to high effort, dev-loop steps to medium, both
configurable via config/agile.yaml's effort_tiers block (mirrors
model_tiers)."""
from promptwise.core.agile_planner import AgilePlanner


def _planner():
    return AgilePlanner(config_path=None)  # hermetic defaults


def test_planning_steps_default_to_high_effort():
    plan = _planner().plan("build a new todo app")
    assert all(s.effort == "high" for s in plan.planning)


def test_dev_loop_steps_default_to_medium_effort():
    plan = _planner().plan("build a new todo app")
    assert all(s.effort == "medium" for s in plan.dev_loop)


def test_to_dict_includes_effort():
    plan = _planner().plan("build a new todo app")
    assert plan.planning[0].to_dict()["effort"] == "high"
