"""Task tracker: add / update / list / report round-trip on a temp sqlite db."""
import asyncio
import os
import tempfile

from promptwise.core import TaskTracker


def _run(coro):
    return asyncio.run(coro)


def test_add_update_list_report():
    async def scenario():
        d = tempfile.mkdtemp()
        path = os.path.join(d, "t.db")
        tt = TaskTracker(path)
        await tt.init()
        a = await tt.add("Build login", estimate_hours=4, status="in_progress", tags=["auth"])
        assert a["task_id"]
        upd = await tt.update(a["task_id"], status="done", actual_hours=5, add_tokens=1200, add_cost=0.03)
        assert upd["status"] == "done"
        assert upd["tokens"] == 1200
        tasks = await tt.list()
        report = await tt.report()
        await tt.engine.dispose()
        return tasks, report

    tasks, report = _run(scenario())
    assert len(tasks) == 1
    assert tasks[0]["actual_hours"] == 5.0
    assert report["total_tasks"] == 1
    assert report["done"] == 1
    assert report["completion_pct"] == 100.0
    assert report["effort_variance_hours"] == 1.0  # 5 actual - 4 estimate
    assert report["total_tokens"] == 1200


def test_update_unknown_task_returns_error():
    async def scenario():
        d = tempfile.mkdtemp()
        path = os.path.join(d, "t.db")
        tt = TaskTracker(path)
        await tt.init()
        res = await tt.update("nope", status="done")
        await tt.engine.dispose()
        return res

    assert _run(scenario())["error"] == "task_not_found"
