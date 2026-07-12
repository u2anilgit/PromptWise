"""``export_stats`` declared ``since``/``format`` params but the handler called
``export_json()`` with no arguments -- every export was all-time JSON no
matter what was requested. Both params must now be honored.
"""
import asyncio
import json
import typing
import uuid
from datetime import datetime, timezone, timedelta

import promptwise.server as s
from promptwise.db.models import MemoryManager, MemoryEntryModel


def _mm(tmp_path):
    mm = MemoryManager(str(tmp_path / "mem.db"))
    asyncio.run(mm.init())
    return mm


async def _seed(mm, days_ago: float, tool: str):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    async with mm.async_session() as session:
        async with session.begin():
            session.add(MemoryEntryModel(entry_id=str(uuid.uuid4()), session_id="s1", ts=ts,
                                         tool=tool, summary="x", cost_usd=0.0, tags="[]"))


def _call(ctx, name, arguments):
    return asyncio.run(typing.cast("typing.Coroutine", s._HANDLERS[name](ctx, arguments)))


def test_export_stats_since_filters_old_rows(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(_seed(mm, 0.1, "recent_tool"))
    asyncio.run(_seed(mm, 10, "old_tool"))

    class _FakeCtx:
        memory = mm

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    out = json.loads(_call(ctx, "export_stats", {"since": cutoff}))
    tools = {e["tool"] for e in out}
    assert tools == {"recent_tool"}


def test_export_stats_csv_format_produces_csv(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(_seed(mm, 0.1, "some_tool"))

    class _FakeCtx:
        memory = mm

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = _call(ctx, "export_stats", {"format": "csv"})
    assert out.splitlines()[0] == "entry_id,session_id,ts,tool,summary,cost_usd,tags"
    assert "some_tool" in out
    assert not out.strip().startswith("[")
