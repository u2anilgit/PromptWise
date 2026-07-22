"""route_request must attach a reasoning-effort level, independent of model
tier -- confirming the effort axis (Tasks 6-7) is wired end-to-end into the
single-call routing path, not just defined in isolation."""
import asyncio
import json
import typing

import promptwise.server as s
from promptwise.core.router import Router


class _FakeMemory:
    async def record_cost(self, **kwargs):
        return None


def test_route_request_response_includes_high_effort(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_EFFORT", "off")

    class _FakeCtx:
        router = Router()
        memory = _FakeMemory()

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = asyncio.run(s._handle_route_request(ctx, {"text": "deploy to production now", "stakes": "high", "intent": "code"}))
    body = json.loads(out)
    assert body["effort"] == "high"


def test_route_request_response_includes_low_effort(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_ADAPTIVE_EFFORT", "off")

    class _FakeCtx:
        router = Router()
        memory = _FakeMemory()

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = asyncio.run(s._handle_route_request(ctx, {"text": "summarize this", "stakes": "low", "intent": "summarize"}))
    body = json.loads(out)
    assert body["effort"] == "low"
