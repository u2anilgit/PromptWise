"""call_tool must apply the response cap to every handler's output -- this
locks in the wiring at the one choke point, not just the pure function."""
import asyncio
import json
import typing

import promptwise.server as s


def test_call_tool_applies_response_cap(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MAX_RESPONSE_ITEMS", "2")

    async def _fake_handler(ctx, arguments):
        return json.dumps({"items": [1, 2, 3, 4, 5]})

    monkeypatch.setitem(s._HANDLERS, "fake_tool_for_cap_test", _fake_handler)
    ctx = typing.cast(s.ServerContext, object())
    out = asyncio.run(s.call_tool(ctx, "fake_tool_for_cap_test", {}))
    body = json.loads(out)
    assert body["items"] == [1, 2]
    assert body["items_truncated_count"] == 3
