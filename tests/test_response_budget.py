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


def test_top_level_list_over_limit_gets_wrapped_and_capped(monkeypatch):
    # get_memory_context / shard_doc return a bare JSON array at the top
    # level, not a dict -- there's no key to hang a sibling
    # "{key}_truncated_count" marker off of, so an over-limit top-level list
    # must be wrapped in an envelope instead of silently passing through.
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "3")
    raw = json.dumps(list(range(10)))
    out = json.loads(cap_response("get_memory_context", raw))
    assert out == {"items": [0, 1, 2], "items_truncated_count": 7}


def test_top_level_list_under_limit_is_unchanged(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "200")
    raw = json.dumps([1, 2, 3])
    assert json.loads(cap_response("shard_doc", raw)) == [1, 2, 3]


def test_top_level_list_items_get_nested_lists_capped(monkeypatch):
    # An over-limit top-level list gets wrapped in an items envelope, but its
    # surviving dict items can themselves carry oversized list-shaped fields
    # -- those must still be capped, not silently passed through.
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "3")
    raw = json.dumps([{"tags": list(range(10))}] * 5)
    out = json.loads(cap_response("some_tool", raw))
    assert out["items_truncated_count"] == 2
    assert len(out["items"]) == 3
    assert out["items"][0]["tags"] == [0, 1, 2]
    assert out["items"][0]["tags_truncated_count"] == 7


def test_top_level_list_under_limit_items_get_nested_lists_capped(monkeypatch):
    # Same nested-capping contract must hold even when the top-level list
    # itself is under the limit and passes through without an envelope.
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "3")
    raw = json.dumps([{"tags": list(range(10))}])
    out = json.loads(cap_response("shard_doc", raw))
    assert out == [{"tags": [0, 1, 2], "tags_truncated_count": 7}]


def test_dict_value_list_of_dicts_is_capped(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "2")
    raw = json.dumps({"tasks": [{"id": i, "name": f"task-{i}"} for i in range(5)]})
    out = json.loads(cap_response("list_tasks", raw))
    assert out["tasks"] == [{"id": 0, "name": "task-0"}, {"id": 1, "name": "task-1"}]
    assert out["tasks_truncated_count"] == 3


def test_dict_value_list_trim_recurses_into_surviving_items(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "2")
    raw = json.dumps({"tasks": [{"tags": list(range(5))} for _ in range(4)]})
    out = json.loads(cap_response("list_tasks", raw))
    assert len(out["tasks"]) == 2
    assert out["tasks_truncated_count"] == 2
    for t in out["tasks"]:
        assert t["tags"] == [0, 1]
        assert t["tags_truncated_count"] == 3


def test_dict_value_list_of_lists_is_capped(monkeypatch):
    # A list nested directly inside another list -- no dict key mediates the
    # inner list, so it gets the {"items": ..., "items_truncated_count": N}
    # envelope in that slot, consistent with the document-root convention.
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "3")
    raw = json.dumps({"matrix": [list(range(10))]})
    out = json.loads(cap_response("some_tool", raw))
    assert out["matrix"] == [{"items": [0, 1, 2], "items_truncated_count": 7}]
    assert "matrix_truncated_count" not in out  # outer list (len 1) was not itself over-limit


def test_top_level_list_of_lists_is_capped(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "3")
    raw = json.dumps([list(range(10)), list(range(10))])
    out = json.loads(cap_response("some_tool", raw))
    # outer list has exactly 2 items, under the limit of 3, so it passes
    # through bare -- but each inner list is over-limit and gets wrapped.
    assert out == [
        {"items": [0, 1, 2], "items_truncated_count": 7},
        {"items": [0, 1, 2], "items_truncated_count": 7},
    ]


def test_deeply_nested_list_of_lists_is_capped_at_every_level(monkeypatch):
    # list-in-list-in-list, all three over the limit -- every level must be
    # capped in a single call, not just the outermost or innermost.
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "2")
    raw = json.dumps([[list(range(5)), list(range(5)), list(range(5))]] * 5)
    out = json.loads(cap_response("some_tool", raw))
    assert out["items_truncated_count"] == 3
    assert len(out["items"]) == 2
    for mid in out["items"]:
        assert mid["items_truncated_count"] == 1
        assert len(mid["items"]) == 2
        for inner in mid["items"]:
            assert inner["items"] == [0, 1]
            assert inner["items_truncated_count"] == 3
