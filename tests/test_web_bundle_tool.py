"""Phase 17.3 — export_web_bundle tool wiring."""
import asyncio
import json
import typing

from promptwise import server as srv


class _Ctx:
    pass


def _call(name, arguments):
    # _Ctx is a lightweight stand-in: this handler doesn't read ctx at all.
    # Cast documents the intentional gap instead of hiding it.
    ctx = typing.cast(srv.ServerContext, _Ctx())
    coro = typing.cast(
        "typing.Coroutine[typing.Any, typing.Any, str]", srv._HANDLERS[name](ctx, arguments)
    )
    return asyncio.run(coro)


def test_tool_registered():
    assert "export_web_bundle" in srv._HANDLERS
    assert any(t.name == "export_web_bundle" for t in srv._TOOL_DEFS)


def test_handler_returns_inline_bundle_by_default():
    out = json.loads(_call("export_web_bundle", {
        "project": "acme", "policy_summary": ["Budget cap $5/day"],
    }))
    assert set(out) == {"bundle", "bytes"}
    assert "acme" in out["bundle"]
    assert "Budget cap $5/day" in out["bundle"]
    assert out["bytes"] > 0


def test_handler_writes_to_out_path(tmp_path):
    dest = tmp_path / "acme-web-agent.md"
    out = json.loads(_call("export_web_bundle", {
        "project": "acme", "out_path": str(dest),
    }))
    assert out["written"] == str(dest)
    assert dest.is_file()
