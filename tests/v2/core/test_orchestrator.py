from promptwise_v2.core.orchestrator import Orchestrator

orc = Orchestrator()


def test_single_step_parse():
    tasks = orc.parse_tasks("Summarize the report")
    assert len(tasks) == 1
    assert tasks[0]["action"] == "summarize"


def test_multi_step_parse():
    tasks = orc.parse_tasks("First read file.py, then refactor the auth function, then run tests")
    assert len(tasks) == 3


def test_dag_build():
    tasks = [{"id": "t1", "action": "read"}, {"id": "t2", "action": "refactor", "depends_on": ["t1"]}]
    dag = orc.build_dag(tasks)
    assert "t2" in dag["t1"]["dependents"]


def test_execute_stop_strategy():
    result = orc.execute("Summarize this text", strategy="stop")
    assert result.status in ("completed", "failed")
    assert result.strategy_used == "stop"


def test_execute_fallback_strategy():
    result = orc.execute("Analyze data trends", strategy="fallback")
    assert result.strategy_used == "fallback"


def test_execute_retry_strategy():
    result = orc.execute("Write a function", strategy="retry")
    assert result.strategy_used == "retry"


def test_steps_accounting():
    result = orc.execute("Read file then summarize", strategy="fallback")
    assert result.steps_total >= 1
    assert result.steps_done <= result.steps_total


def test_cost_tracked():
    result = orc.execute("Hello", strategy="stop")
    assert result.cost_usd >= 0.0
