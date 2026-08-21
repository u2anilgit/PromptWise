from promptwise.core.task_graph import plan_waves


def test_backward_compatible_when_no_fleet_args_given():
    tasks = [{"id": "a"}, {"id": "b"}]
    plan = plan_waves(tasks)
    assert plan["waves"] == [["a", "b"]]
    assert plan["over_budget"] == []


def test_over_budget_agent_task_excluded_from_waves():
    tasks = [
        {"id": "a", "agent_id": "agent-rich"},
        {"id": "b", "agent_id": "agent-broke"},
    ]
    plan = plan_waves(tasks, agent_budget_status={
        "agent-rich": {"remaining_usd": 10.0}, "agent-broke": {"remaining_usd": 0.0}})
    assert plan["waves"] == [["a"]]
    assert plan["over_budget"] == ["b"]


def test_negative_remaining_budget_also_excluded():
    tasks = [{"id": "a", "agent_id": "agent-x"}]
    plan = plan_waves(tasks, agent_budget_status={"agent-x": {"remaining_usd": -5.0}})
    assert plan["waves"] == []
    assert plan["over_budget"] == ["a"]


def test_high_priority_agent_survives_fan_out_cap():
    tasks = [
        {"id": "low1", "agent_id": "agent-low"}, {"id": "low2", "agent_id": "agent-low"},
        {"id": "high1", "agent_id": "agent-high"},
    ]
    plan = plan_waves(
        tasks, fan_out_cap=2,
        agent_priority={"agent-low": "low", "agent-high": "high"})
    assert "high1" in plan["waves"][0]
    assert plan["capped"] is True


def test_no_agent_id_tasks_unaffected_by_priority_map():
    tasks = [{"id": "a"}, {"id": "b"}]
    plan = plan_waves(tasks, agent_priority={"agent-x": "high"})
    assert plan["waves"] == [["a", "b"]]
