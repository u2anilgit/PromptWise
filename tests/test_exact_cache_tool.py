"""Phase 15 — ExactCache MCP tool wiring: cache_lookup / cache_store / cache_stats."""
import asyncio
import json
import typing

from promptwise import server as srv
from promptwise.core.exact_cache import ExactCache


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


def test_tools_registered():
    for name in ("cache_lookup", "cache_store", "cache_stats"):
        assert name in srv._HANDLERS
        assert any(t.name == name for t in srv._TOOL_DEFS)


def test_lookup_is_a_miss_before_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("promptwise.core.exact_cache._default_db", lambda: tmp_path / "pw.db")
    out = json.loads(_call("cache_lookup", {"tool": "route_request", "request": {"text": "hi"}}))
    assert out["hit"] is False


def test_store_then_lookup_hits(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.exact_cache._default_db", lambda: tmp_path / "pw.db")
    stored = json.loads(_call("cache_store", {
        "tool": "route_request", "request": {"text": "deploy it"},
        "result": {"tier": "sonnet"}, "category": "routing"}))
    assert stored["stored"] is True

    got = json.loads(_call("cache_lookup", {"tool": "route_request", "request": {"text": "deploy it"}}))
    assert got["hit"] is True
    assert got["value"] == {"tier": "sonnet"}


def test_store_refuses_never_cache_category(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.exact_cache._default_db", lambda: tmp_path / "pw.db")
    stored = json.loads(_call("cache_store", {
        "tool": "some_tool", "request": {"text": "x"}, "result": {"v": 1}, "category": "medical"}))
    assert stored["stored"] is False
    assert "medical" in stored["reason"]


def test_stats_reports_hits_and_entries(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.exact_cache._default_db", lambda: tmp_path / "pw.db")
    _call("cache_store", {"tool": "t", "request": {"text": "a"}, "result": {"v": 1}})
    _call("cache_lookup", {"tool": "t", "request": {"text": "a"}})
    out = json.loads(_call("cache_stats", {}))
    assert out["entries"] == 1
    assert out["hits"] == 1
    assert set(out) == {"entries", "hits", "misses", "hit_rate", "by_category"}


def test_stats_purges_expired_by_default(tmp_path):
    db = tmp_path / "pw.db"
    cache = ExactCache(db, default_ttl_seconds=1)
    cache.put("t", {"text": "a"}, {"v": 1}, ts=1_000_000.0)

    import promptwise.core.exact_cache as ec_module
    orig = ec_module._default_db
    ec_module._default_db = lambda: db
    try:
        # purge_expired() with the real clock will see this timestamp as long
        # past its 1s TTL (ts is 1970-relative, real "now" is decades later).
        stats_coro = typing.cast(
            "typing.Coroutine[typing.Any, typing.Any, str]",
            srv._HANDLERS["cache_stats"](typing.cast(srv.ServerContext, _Ctx()), {"purge_expired": True}),
        )
        out = json.loads(asyncio.run(stats_coro))
    finally:
        ec_module._default_db = orig
    assert out["entries"] == 0
