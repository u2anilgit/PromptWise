"""execute_autonomous() used to run an identical scripted plan/execute/test/fix
state machine regardless of the ``task`` string, including a hardcoded
"Tests passed successfully" claim about tests it never ran. It must now
decompose the real task text (same parser execute() uses) and never
fabricate a pass/fail verdict.
"""
from promptwise.core.orchestrator import Orchestrator


def test_different_tasks_produce_different_history():
    o = Orchestrator()
    a = o.execute_autonomous("write a function to parse CSV")
    b = o.execute_autonomous("summarize the quarterly report")
    assert a["history"] != b["history"]
    assert a["history"][0]["details"] != b["history"][0]["details"]


def test_never_claims_tests_passed_it_never_ran():
    o = Orchestrator()
    result = o.execute_autonomous("delete all user records")
    for step in result["history"]:
        assert step["status"] != "success"
        assert "Tests passed" not in step["details"]
        assert "SyntaxError" not in step["details"]


def test_respects_max_iterations_cap():
    o = Orchestrator()
    result = o.execute_autonomous("first do this. then do that. next do the other thing.", max_iterations=1)
    assert result["iterations_run"] == 1
    assert result["status"] == "partial"
    assert result["success"] is False
