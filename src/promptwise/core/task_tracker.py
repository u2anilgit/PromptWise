"""Task tracker — effort + token + cost tracking, sqlite-backed, self-contained.

Lets end users track development tasks with estimated vs actual effort, token usage,
and cost. Reuses the PromptWise db (TaskModel on the shared Base). No external services.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from promptwise.db.models import Base, TaskModel

_VALID_STATUS = {"todo", "in_progress", "blocked", "done"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(t: TaskModel) -> dict:
    return {
        "task_id": t.task_id, "title": t.title, "status": t.status,
        "estimate_hours": t.estimate_hours, "actual_hours": t.actual_hours,
        "tokens": t.tokens, "cost_usd": round(t.cost_usd, 6),
        "tags": json.loads(t.tags or "[]"),
        "created_ts": t.created_ts, "updated_ts": t.updated_ts,
    }


class TaskTracker:
    def __init__(self, db_path: Path | str):
        db_url = str(db_path)
        if not db_url.startswith(("sqlite", "postgresql")):
            db_url = f"sqlite+aiosqlite:///{db_path}"
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def add(self, title: str, estimate_hours: float = 0.0,
                  status: str = "todo", tags: list[str] | None = None) -> dict:
        if status not in _VALID_STATUS:
            status = "todo"
        task_id = uuid.uuid4().hex[:8]
        ts = _now()
        async with self.async_session() as session:
            async with session.begin():
                session.add(TaskModel(
                    task_id=task_id, title=title, status=status,
                    estimate_hours=float(estimate_hours or 0.0),
                    tags=json.dumps(tags or []), created_ts=ts, updated_ts=ts))
        return {"task_id": task_id, "title": title, "status": status,
                "estimate_hours": float(estimate_hours or 0.0)}

    async def update(self, task_id: str, status: str | None = None,
                     actual_hours: float | None = None, tokens: float | None = None,
                     cost_usd: float | None = None, add_tokens: float | None = None,
                     add_cost: float | None = None) -> dict:
        async with self.async_session() as session:
            stmt = select(TaskModel).where(TaskModel.task_id == task_id)
            res = await session.execute(stmt)
            t = res.scalar_one_or_none()
            if not t:
                return {"error": "task_not_found", "task_id": task_id}
            if status and status in _VALID_STATUS:
                t.status = status
            if actual_hours is not None:
                t.actual_hours = float(actual_hours)
            if tokens is not None:
                t.tokens = float(tokens)
            if cost_usd is not None:
                t.cost_usd = float(cost_usd)
            if add_tokens:
                t.tokens = (t.tokens or 0.0) + float(add_tokens)
            if add_cost:
                t.cost_usd = (t.cost_usd or 0.0) + float(add_cost)
            t.updated_ts = _now()
            await session.flush()
            row = _row(t)
            await session.commit()
        return row

    async def list(self, status: str | None = None) -> list[dict]:
        async with self.async_session() as session:
            stmt = select(TaskModel)
            if status:
                stmt = stmt.where(TaskModel.status == status)
            stmt = stmt.order_by(TaskModel.created_ts)
            res = await session.execute(stmt)
            return [_row(t) for t in res.scalars().all()]

    async def report(self) -> dict:
        tasks = await self.list()
        by_status: dict[str, int] = {}
        for t in tasks:
            by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        est = sum(t["estimate_hours"] for t in tasks)
        act = sum(t["actual_hours"] for t in tasks)
        return {
            "total_tasks": len(tasks),
            "by_status": by_status,
            "estimate_hours": round(est, 2),
            "actual_hours": round(act, 2),
            "effort_variance_hours": round(act - est, 2),
            "total_tokens": round(sum(t["tokens"] for t in tasks), 0),
            "total_cost_usd": round(sum(t["cost_usd"] for t in tasks), 6),
            "done": by_status.get("done", 0),
            "completion_pct": round(100 * by_status.get("done", 0) / len(tasks), 1) if tasks else 0.0,
        }
