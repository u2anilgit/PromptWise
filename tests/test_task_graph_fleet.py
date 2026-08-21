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


def test_over_budget_exclusion_cascades_to_transitive_dependents():
    """a is over budget; b depends_on a; b must also land in over_budget
    (transitively unschedulable), not in any wave, even though b's own
    agent has plenty of budget."""
    tasks = [
        {"id": "a", "agent_id": "agent-broke"},
        {"id": "b", "agent_id": "agent-rich", "depends_on": ["a"]},
    ]
    plan = plan_waves(tasks, agent_budget_status={
        "agent-broke": {"remaining_usd": 0.0}, "agent-rich": {"remaining_usd": 10.0}})
    assert plan["over_budget"] == ["a", "b"]
    scheduled = [i for w in plan["waves"] for i in w]
    assert "a" not in scheduled
    assert "b" not in scheduled


def test_over_budget_exclusion_cascades_transitively_multi_hop():
    """a over budget -> b depends_on a -> c depends_on b: all three must
    end up in over_budget, not just the direct dependent."""
    tasks = [
        {"id": "a", "agent_id": "agent-broke"},
        {"id": "b", "depends_on": ["a"]},
        {"id": "c", "depends_on": ["b"]},
    ]
    plan = plan_waves(tasks, agent_budget_status={"agent-broke": {"remaining_usd": 0.0}})
    assert plan["over_budget"] == ["a", "b", "c"]
    assert plan["waves"] == []
