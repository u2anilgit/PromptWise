"""Phase 11 WP11.3 — run_red_team_harness tool wiring."""
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
    assert "run_red_team_harness" in srv._HANDLERS
    assert any(t.name == "run_red_team_harness" for t in srv._TOOL_DEFS)


def test_defaults_to_builtin_corpus_and_passes(tmp_path, monkeypatch):
    from promptwise.core import redteam_harness as rth
    monkeypatch.setattr(rth, "_default_db", lambda: tmp_path / "rt.db")

    out = json.loads(_call("run_red_team_harness", {}))
    assert out["gate"] == "pass"
    assert out["counts"]["cases"] == 14


def test_save_baseline_flag(tmp_path, monkeypatch):
    from promptwise.core import redteam_harness as rth
    monkeypatch.setattr(rth, "_default_db", lambda: tmp_path / "rt.db")

    out = json.loads(_call("run_red_team_harness", {"save_baseline": True}))
    assert out["baseline_saved"] == 14
