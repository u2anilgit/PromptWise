"""``get_roi_stats(period=...)`` used to ignore ``period`` entirely and always
return all-time rows -- ``get_roi_report``/``cost_report`` returned identical
totals for daily/weekly/monthly. It must filter to the requested window.
"""
import asyncio
import json
import typing
import uuid
from datetime import datetime, timezone, timedelta

import promptwise.server as s
from promptwise.db.models import MemoryManager, ROIStatModel


def _mm(tmp_path):
    mm = MemoryManager(str(tmp_path / "mem.db"))
    asyncio.run(mm.init())
    return mm


async def _seed(mm, days_ago: float, cost_usd: float):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    async with mm.async_session() as session:
        async with session.begin():
            session.add(ROIStatModel(stat_id=str(uuid.uuid4()), developer="d", role="Dev", skill="",
                                     project_id="", tokens_saved=0, cost_usd=cost_usd, hours_saved=0, ts=ts))


def test_get_roi_stats_daily_excludes_old_rows(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(_seed(mm, 0.1, 1.0))   # within last day
    asyncio.run(_seed(mm, 10, 2.0))    # 10 days old -- outside daily/weekly window

    daily = asyncio.run(mm.get_roi_stats(period="daily"))
    assert [r["cost_usd"] for r in daily] == [1.0]

    all_time = asyncio.run(mm.get_roi_stats(period="all"))
    assert len(all_time) == 2


def test_get_roi_stats_weekly_vs_monthly_differ(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(_seed(mm, 3, 1.0))     # within week
    asyncio.run(_seed(mm, 20, 2.0))    # within month, not week

    weekly = asyncio.run(mm.get_roi_stats(period="weekly"))
    monthly = asyncio.run(mm.get_roi_stats(period="monthly"))
    assert sum(r["cost_usd"] for r in weekly) == 1.0
    assert sum(r["cost_usd"] for r in monthly) == 3.0


def test_get_roi_report_handler_passes_period_through(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(_seed(mm, 0.1, 1.0))
    asyncio.run(_seed(mm, 20, 5.0))

    class _FakeCtx:
        memory = mm

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    daily = json.loads(asyncio.run(s._handle_get_roi_report(ctx, {"period": "daily"})))
    monthly = json.loads(asyncio.run(s._handle_get_roi_report(ctx, {"period": "monthly"})))
    assert daily["total_cost_usd"] == 1.0
    assert monthly["total_cost_usd"] == 6.0
