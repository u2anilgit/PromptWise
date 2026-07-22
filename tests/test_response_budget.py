"""No PromptWise tool response was ever size-capped -- list_tasks,
search_trace, run_security_suite could return unbounded JSON (every
optimization tool shrinks the prompt going INTO a model call; nothing
shrunk PromptWise's own responses coming back). cap_response keeps only the
first N items of any over-limit list-shaped field, except for tools where
the full payload is the point (exports)."""
import json

from promptwise.core.response_budget import cap_response


def test_large_list_gets_capped_with_marker(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "3")
    raw = json.dumps({"tasks": list(range(10))})
    out = json.loads(cap_response("list_tasks", raw))
    assert out["tasks"] == [0, 1, 2]
    assert out["tasks_truncated_count"] == 7


def test_small_list_is_unchanged(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "200")
    raw = json.dumps({"tasks": [1, 2, 3]})
    assert json.loads(cap_response("list_tasks", raw)) == {"tasks": [1, 2, 3]}


def test_exempt_tool_is_never_capped(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "1")
    raw = json.dumps({"records": [1, 2, 3, 4, 5]})
    assert json.loads(cap_response("export_audit", raw)) == {"records": [1, 2, 3, 4, 5]}


def test_unparseable_json_passes_through_unchanged():
    assert cap_response("list_tasks", "not json") == "not json"


def test_nested_lists_are_capped_too(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "2")
    raw = json.dumps({"breakdowns": {"by_skill": list(range(5))}})
    out = json.loads(cap_response("some_tool", raw))
    assert out["breakdowns"]["by_skill"] == [0, 1]
    assert out["breakdowns"]["by_skill_truncated_count"] == 3
