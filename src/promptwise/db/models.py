import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sqlalchemy import String, Float, Text, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy.future import select

from promptwise.types import MemoryEntry

Base = declarative_base()


class SessionModel(Base):
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    started_ts: Mapped[str] = mapped_column(String(50), nullable=False)
    last_ping_ts: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[str] = mapped_column(String(10), default="true")


class CostLogModel(Base):
    __tablename__ = "cost_logs"
    log_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ts: Mapped[str] = mapped_column(String(50), nullable=False)
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[float] = mapped_column(Float, default=0.0)
    output_tokens: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    saving_pct: Mapped[float] = mapped_column(Float, default=0.0)
    lines: Mapped[float] = mapped_column(Float, default=0.0)


class MemoryEntryModel(Base):
    __tablename__ = "memory_entries"
    entry_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ts: Mapped[str] = mapped_column(String(50), nullable=False)
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tags: Mapped[str] = mapped_column(Text, default="[]")


class SemanticFactModel(Base):
    __tablename__ = "semantic_facts"
    fact_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(50), default="org")


class PromptModel(Base):
    __tablename__ = "prompts"
    prompt_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    ts: Mapped[str] = mapped_column(String(50), nullable=False)


class ROIStatModel(Base):
    __tablename__ = "roi_stats"
    stat_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    developer: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    skill: Mapped[str] = mapped_column(String(100), default="")
    project_id: Mapped[str] = mapped_column(String(100), default="")
    tokens_saved: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    hours_saved: Mapped[float] = mapped_column(Float, default=0.0)
    ts: Mapped[str] = mapped_column(String(50), nullable=False)


class TaskModel(Base):
    __tablename__ = "tasks"
    task_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="todo", index=True)  # todo|in_progress|blocked|done
    estimate_hours: Mapped[float] = mapped_column(Float, default=0.0)
    actual_hours: Mapped[float] = mapped_column(Float, default=0.0)
    tokens: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tags: Mapped[str] = mapped_column(Text, default="[]")
    created_ts: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_ts: Mapped[str] = mapped_column(String(50), nullable=False)


class RouteOutcomeModel(Base):
    """Phase 7 WP7.1 — per-route-decision outcome for the adaptive learning loop.

    Additive, append-only feedback store. ``quality_signal`` is a normalized
    ``met`` / ``not_met`` / ``neutral`` verdict (absence is neutral, never
    negative). The sync ``core.adaptive_router.OutcomeStore`` reads/writes the
    same ``route_outcomes`` table for the routing hot path.
    """
    __tablename__ = "route_outcomes"
    outcome_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ts: Mapped[str] = mapped_column(String(50), nullable=False)
    task_class: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    model_family: Mapped[str] = mapped_column(String(100), default="")
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    quality_signal: Mapped[str] = mapped_column(String(20), default="neutral")


class EvalResultModel(Base):
    """Phase 7 WP7.3 — one scored eval-case result for the regression harness.

    Additive, append-only. Mirrors the sync ``core.eval_harness.EvalResultStore``
    which reads/writes the same ``eval_results`` table on the local DB. ``verdict``
    is the normalized ``met`` / ``not_met`` bar decision; ``mode`` is ``local``
    (ran on an on-device runtime) or ``record`` (offline dry-run).
    """
    __tablename__ = "eval_results"
    result_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ts: Mapped[str] = mapped_column(String(50), nullable=False)
    suite: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)
    case_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    task_class: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(20), default="not_met")
    mode: Mapped[str] = mapped_column(String(20), default="record")
    signals: Mapped[str] = mapped_column(Text, default="[]")


class EvalBaselineModel(Base):
    """Phase 7 WP7.3 — the blessed baseline a run is diffed against to flag drift.

    Keyed by (suite, case_id, tier) so a baseline is per-tier. Upserted by the
    sync ``EvalResultStore`` on the same ``eval_baselines`` table.
    """
    __tablename__ = "eval_baselines"
    suite: Mapped[str] = mapped_column(String(100), primary_key=True, default="default")
    case_id: Mapped[str] = mapped_column(String(100), primary_key=True, default="")
    tier: Mapped[str] = mapped_column(String(20), primary_key=True, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(20), default="not_met")
    ts: Mapped[str] = mapped_column(String(50), nullable=False)


def get_db_path() -> Path:
    db_dir = Path.home() / ".promptwise"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "promptwise.db"


async def init_db(db_path: Path | str | None = None) -> str:
    if db_path is None:
        db_path = get_db_path()
    db_path = Path(db_path)
    db_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    return str(db_path)


class SessionManager:
    def __init__(self, db_path: Path | str):
        db_url = f"sqlite+aiosqlite:///{db_path}"
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def ping(self, session_id: str | None = None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        if not session_id:
            session_id = str(uuid.uuid4())
            async with self.async_session() as session:
                async with session.begin():
                    session.add(SessionModel(session_id=session_id, started_ts=now, last_ping_ts=now))
            return {"session_id": session_id, "started_ts": now, "last_ping_ts": now, "is_new": True}

        async with self.async_session() as session:
            stmt = select(SessionModel).where(SessionModel.session_id == session_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                model.last_ping_ts = now
                await session.flush()
                return {"session_id": session_id, "started_ts": model.started_ts, "last_ping_ts": now, "is_new": False}

        async with self.async_session() as session:
            async with session.begin():
                session.add(SessionModel(session_id=session_id, started_ts=now, last_ping_ts=now))
        return {"session_id": session_id, "started_ts": now, "last_ping_ts": now, "is_new": True}

    async def check_timeout(self, session_id: str, idle_threshold_minutes: int = 30, warn_threshold_minutes: int = 20) -> dict:
        async with self.async_session() as session:
            stmt = select(SessionModel).where(SessionModel.session_id == session_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                return {"session_id": session_id, "status": "not_found", "idle_minutes": 0, "recommended_action": "create_new", "message": "Session not found"}

        last_ping = datetime.fromisoformat(model.last_ping_ts)
        idle_minutes = (datetime.now(timezone.utc) - last_ping).total_seconds() / 60

        if idle_minutes >= idle_threshold_minutes:
            status = "expired"
            action = "summarize_and_exit"
            msg = f"Session expired after {idle_minutes:.0f} minutes idle"
        elif idle_minutes >= warn_threshold_minutes:
            status = "warn"
            action = "prompt_user"
            msg = f"Session idle for {idle_minutes:.0f} minutes (warn threshold: {warn_threshold_minutes}m)"
        else:
            status = "active"
            action = "none"
            msg = f"Session active, idle {idle_minutes:.0f} minutes"

        return {"session_id": session_id, "status": status, "idle_minutes": round(idle_minutes, 1), "recommended_action": action, "message": msg}


class MemoryManager:
    def __init__(self, db_url: str):
        if not db_url.startswith("sqlite") and not db_url.startswith("postgresql"):
            db_url = f"sqlite+aiosqlite:///{db_url}"
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def log(self, *, session_id: str, tool: str, summary: str, cost_usd: float = 0.0, tags: list[str] | None = None) -> MemoryEntry:
        entry_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags or [])
        async with self.async_session() as session:
            async with session.begin():
                session.add(MemoryEntryModel(entry_id=entry_id, session_id=session_id, ts=ts, tool=tool, summary=summary, cost_usd=cost_usd, tags=tags_json))
        return MemoryEntry(entry_id=entry_id, session_id=session_id, ts=ts, tool=tool, summary=summary, cost_usd=cost_usd, tags=tags or [])

    async def get_context(self, session_id: str, limit: int = 20) -> list[MemoryEntry]:
        async with self.async_session() as session:
            stmt = select(MemoryEntryModel).where(MemoryEntryModel.session_id == session_id).order_by(MemoryEntryModel.ts.desc()).limit(limit)
            result = await session.execute(stmt)
            entries = result.scalars().all()
        return [MemoryEntry(entry_id=e.entry_id, session_id=e.session_id, ts=e.ts, tool=e.tool, summary=e.summary, cost_usd=e.cost_usd, tags=json.loads(e.tags)) for e in entries]

    async def save_fact(self, key: str, value: str, scope: str = "org") -> None:
        # Upsert by (key, scope): refresh an existing fact instead of piling up
        # duplicate rows that all surface in query_facts.
        ts = datetime.now(timezone.utc).isoformat()
        async with self.async_session() as session:
            async with session.begin():
                stmt = select(SemanticFactModel).where(
                    SemanticFactModel.key == key, SemanticFactModel.scope == scope)
                existing = (await session.execute(stmt)).scalars().first()
                if existing is not None:
                    existing.value = value
                    existing.ts = ts
                else:
                    session.add(SemanticFactModel(fact_id=str(uuid.uuid4()), key=key, value=value, ts=ts, scope=scope))

    async def query_facts(self, query: str) -> list[dict]:
        async with self.async_session() as session:
            stmt = (select(SemanticFactModel)
                    .where(SemanticFactModel.key.contains(query) | SemanticFactModel.value.contains(query))
                    .order_by(SemanticFactModel.ts.desc()))
            result = await session.execute(stmt)
            facts = result.scalars().all()
        # Rank by query-term overlap first, then recency (rows already ts-desc).
        terms = [t for t in re.findall(r"[a-zA-Z0-9_]+", (query or "").lower()) if len(t) > 1]

        def _score(f) -> int:
            hay = f"{f.key} {f.value}".lower()
            return sum(hay.count(t) for t in terms)

        ranked = sorted(facts, key=_score, reverse=True) if terms else list(facts)
        return [{"key": f.key, "value": f.value, "scope": f.scope} for f in ranked]

    async def save_prompt(self, name: str, content: str, version: str = "1.0.0", description: str = "", tags: list[str] | None = None) -> None:
        async with self.async_session() as session:
            async with session.begin():
                session.add(PromptModel(prompt_id=str(uuid.uuid4()), name=name, content=content, version=version, description=description, tags=json.dumps(tags or []), ts=datetime.now(timezone.utc).isoformat()))

    async def search_prompts(self, query: str) -> list[dict]:
        async with self.async_session() as session:
            stmt = (select(PromptModel)
                    .where(PromptModel.name.contains(query) | PromptModel.description.contains(query))
                    .order_by(PromptModel.ts.desc()))
            result = await session.execute(stmt)
            prompts = result.scalars().all()
        return [{"name": p.name, "content": p.content, "version": p.version, "description": p.description, "tags": json.loads(p.tags)} for p in prompts]

    async def log_roi_stat(self, developer: str, role: str, tokens_saved: float, cost_usd: float, hours_saved: float, skill: str = "", project_id: str = "") -> None:
        async with self.async_session() as session:
            async with session.begin():
                session.add(ROIStatModel(stat_id=str(uuid.uuid4()), developer=developer, role=role, skill=skill, project_id=project_id, tokens_saved=tokens_saved, cost_usd=cost_usd, hours_saved=hours_saved, ts=datetime.now(timezone.utc).isoformat()))

    async def get_roi_stats(self, period: str = "all") -> list[dict]:
        window_days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period)
        async with self.async_session() as session:
            stmt = select(ROIStatModel).order_by(ROIStatModel.ts.desc())
            if window_days is not None:
                since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
                stmt = stmt.where(ROIStatModel.ts >= since)
            result = await session.execute(stmt)
            stats = result.scalars().all()
        return [{"developer": s.developer, "role": s.role, "skill": s.skill, "project_id": s.project_id, "tokens_saved": s.tokens_saved, "cost_usd": s.cost_usd, "hours_saved": s.hours_saved, "ts": s.ts} for s in stats]

    async def prune(self, retention_weeks: int = 4) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(weeks=retention_weeks)).isoformat()
        async with self.async_session() as session:
            async with session.begin():
                stmt = select(MemoryEntryModel).where(MemoryEntryModel.ts < cutoff)
                result = await session.execute(stmt)
                entries = result.scalars().all()
                count = len(entries)
                for entry in entries:
                    await session.delete(entry)
        return count

    async def export_json(self) -> str:
        async with self.async_session() as session:
            stmt = select(MemoryEntryModel).order_by(MemoryEntryModel.ts)
            result = await session.execute(stmt)
            entries = result.scalars().all()
        return json.dumps([{"entry_id": e.entry_id, "session_id": e.session_id, "ts": e.ts, "tool": e.tool, "summary": e.summary, "cost_usd": e.cost_usd, "tags": json.loads(e.tags)} for e in entries], indent=2)

    async def clear_old(self, older_than_days: int = 90) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        async with self.async_session() as session:
            async with session.begin():
                stmt = select(CostLogModel).where(CostLogModel.ts < cutoff)
                result = await session.execute(stmt)
                entries = result.scalars().all()
                count = len(entries)
                for entry in entries:
                    await session.delete(entry)
        return count

    async def record_route_outcome(self, *, task_class: str, tier: str, quality_signal: object = "neutral",
                                   model_family: str = "", cost: float = 0.0) -> str:
        """Persist a route-decision outcome for the adaptive loop (async path,
        e.g. the eval harness). Returns the normalized signal stored."""
        from promptwise.core.adaptive_router import normalize_quality_signal
        signal = normalize_quality_signal(quality_signal)
        async with self.async_session() as session:
            async with session.begin():
                session.add(RouteOutcomeModel(
                    outcome_id=str(uuid.uuid4()), ts=datetime.now(timezone.utc).isoformat(),
                    task_class=task_class, tier=tier, model_family=model_family,
                    cost=cost, quality_signal=signal))
        return signal

    async def get_route_outcomes(self, task_class: str | None = None) -> list[dict]:
        async with self.async_session() as session:
            stmt = select(RouteOutcomeModel)
            if task_class:
                stmt = stmt.where(RouteOutcomeModel.task_class == task_class)
            stmt = stmt.order_by(RouteOutcomeModel.ts)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [{"task_class": r.task_class, "tier": r.tier, "model_family": r.model_family,
                 "cost": r.cost, "quality_signal": r.quality_signal, "ts": r.ts} for r in rows]

    async def record_eval_result(self, *, suite: str, case_id: str, task_class: str, tier: str,
                                 score: float, verdict: str, mode: str = "record",
                                 signals: list[str] | None = None) -> None:
        """Persist one scored eval result (async path). Mirrors the sync
        ``core.eval_harness.EvalResultStore.record_result`` on the same table."""
        async with self.async_session() as session:
            async with session.begin():
                session.add(EvalResultModel(
                    result_id=str(uuid.uuid4()), ts=datetime.now(timezone.utc).isoformat(),
                    suite=suite, case_id=case_id, task_class=task_class, tier=tier,
                    score=score, verdict=verdict, mode=mode,
                    signals=json.dumps(signals or [])))

    async def get_eval_results(self, suite: str | None = None) -> list[dict]:
        async with self.async_session() as session:
            stmt = select(EvalResultModel)
            if suite:
                stmt = stmt.where(EvalResultModel.suite == suite)
            stmt = stmt.order_by(EvalResultModel.ts)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [{"suite": r.suite, "case_id": r.case_id, "task_class": r.task_class,
                 "tier": r.tier, "score": r.score, "verdict": r.verdict, "mode": r.mode,
                 "signals": json.loads(r.signals), "ts": r.ts} for r in rows]

    async def record_cost(self, *, session_id: str, tool: str, model: str, input_tokens: float = 0, output_tokens: float = 0, cost_usd: float = 0, saving_pct: float = 0, lines: float = 0) -> None:
        async with self.async_session() as session:
            async with session.begin():
                session.add(CostLogModel(log_id=str(uuid.uuid4()), session_id=session_id, ts=datetime.now(timezone.utc).isoformat(), tool=tool, model=model, input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost_usd, saving_pct=saving_pct, lines=lines))

    async def raw_cost_logs(self, since: str | None = None) -> list[dict]:
        """Raw cost events (optionally since an ISO cutoff) for the dashboard's
        retention/rollup layer."""
        async with self.async_session() as session:
            stmt = select(CostLogModel)
            if since:
                stmt = stmt.where(CostLogModel.ts >= since)
            stmt = stmt.order_by(CostLogModel.ts)
            result = await session.execute(stmt)
            logs = result.scalars().all()
        return [{"ts": l.ts, "session_id": l.session_id, "tool": l.tool, "model": l.model,
                 "input_tokens": l.input_tokens, "output_tokens": l.output_tokens,
                 "cost_usd": l.cost_usd, "saving_pct": l.saving_pct,
                 "lines": getattr(l, "lines", 0) or 0} for l in logs]

    async def snapshot(self, since: str | None = None) -> dict:
        async with self.async_session() as session:
            stmt = select(CostLogModel)
            if since:
                stmt = stmt.where(CostLogModel.ts >= since)
            result = await session.execute(stmt)
            logs = result.scalars().all()
        total_calls = len(logs)
        total_cost = sum(l.cost_usd for l in logs)
        savings = [l.saving_pct for l in logs if l.saving_pct]
        avg_saving = sum(savings) / len(savings) if savings else 0.0
        calls_by_tool = {}
        cost_by_model = {}
        for l in logs:
            calls_by_tool[l.tool] = calls_by_tool.get(l.tool, 0) + 1
            cost_by_model[l.model] = cost_by_model.get(l.model, 0) + l.cost_usd
        return {"total_calls": total_calls, "total_cost_usd": round(total_cost, 6), "avg_saving_pct": round(avg_saving, 1), "calls_by_tool": calls_by_tool, "cost_by_model": cost_by_model}
