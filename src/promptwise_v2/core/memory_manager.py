import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import Column, String, Float, Text, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.future import select

Base = declarative_base()


class MemoryEntryModel(Base):
    __tablename__ = "memory_entries"
    entry_id = Column(String(50), primary_key=True)
    session_id = Column(String(50), nullable=False, index=True)
    ts = Column(String(50), nullable=False)
    tool = Column(String(100), nullable=False)
    summary = Column(Text, nullable=False)
    cost_usd = Column(Float, default=0.0)
    tags = Column(Text, default="[]")


class SemanticFactModel(Base):
    __tablename__ = "semantic_facts"
    fact_id = Column(String(50), primary_key=True)
    key = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=False)
    ts = Column(String(50), nullable=False)
    scope = Column(String(50), default="org")  # "session" or "org"


class PromptModel(Base):
    __tablename__ = "prompts"
    prompt_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    content = Column(Text, nullable=False)
    version = Column(String(20), nullable=False)
    description = Column(Text, default="")
    tags = Column(Text, default="[]")
    ts = Column(String(50), nullable=False)


class ROIStatModel(Base):
    __tablename__ = "roi_stats"
    stat_id = Column(String(50), primary_key=True)
    developer = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    tokens_saved = Column(Float, default=0.0)
    cost_usd = Column(Float, default=0.0)
    hours_saved = Column(Float, default=0.0)
    ts = Column(String(50), nullable=False)


class MemoryManager:
    def __init__(self, db_url: str):
        if not isinstance(db_url, str):
            db_url = str(db_url)

        if not db_url.startswith("sqlite") and not db_url.startswith("postgresql"):
            db_url = f"sqlite+aiosqlite:///{db_url}"

        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def log(self, *, session_id: str, tool: str, summary: str,
                  cost_usd: float = 0.0, tags: list[str] | None = None) -> object:
        from promptwise_v2.types_v2 import MemoryEntry
        entry_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags or [])

        async with self.async_session() as session:
            async with session.begin():
                entry = MemoryEntryModel(
                    entry_id=entry_id,
                    session_id=session_id,
                    ts=ts,
                    tool=tool,
                    summary=summary,
                    cost_usd=cost_usd,
                    tags=tags_json,
                )
                session.add(entry)

        return MemoryEntry(
            entry_id=entry_id,
            session_id=session_id,
            ts=ts,
            tool=tool,
            summary=summary,
            cost_usd=cost_usd,
            tags=tags or [],
        )

    async def get_context(self, session_id: str, limit: int = 20) -> list:
        from promptwise_v2.types_v2 import MemoryEntry
        async with self.async_session() as session:
            stmt = (
                select(MemoryEntryModel)
                .where(MemoryEntryModel.session_id == session_id)
                .order_by(MemoryEntryModel.ts.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            entries = result.scalars().all()

        return [
            MemoryEntry(
                entry_id=e.entry_id,
                session_id=e.session_id,
                ts=e.ts,
                tool=e.tool,
                summary=e.summary,
                cost_usd=e.cost_usd,
                tags=json.loads(e.tags),
            )
            for e in entries
        ]

    async def save_fact(self, key: str, value: str, scope: str = "org") -> None:
        async with self.async_session() as session:
            async with session.begin():
                fact = SemanticFactModel(
                    fact_id=str(uuid.uuid4()),
                    key=key,
                    value=value,
                    ts=datetime.now(timezone.utc).isoformat(),
                    scope=scope,
                )
                session.add(fact)

    async def query_facts(self, query: str) -> list[dict]:
        async with self.async_session() as session:
            stmt = select(SemanticFactModel).where(
                SemanticFactModel.key.like(f"%{query}%") | SemanticFactModel.value.like(f"%{query}%")
            )
            result = await session.execute(stmt)
            facts = result.scalars().all()
        return [{"key": f.key, "value": f.value, "scope": f.scope} for f in facts]

    async def save_prompt(self, name: str, content: str, version: str, description: str = "", tags: list[str] = None) -> None:
        async with self.async_session() as session:
            async with session.begin():
                p = PromptModel(
                    prompt_id=str(uuid.uuid4()),
                    name=name,
                    content=content,
                    version=version,
                    description=description,
                    tags=json.dumps(tags or []),
                    ts=datetime.now(timezone.utc).isoformat(),
                )
                session.add(p)

    async def search_prompts(self, query: str) -> list[dict]:
        async with self.async_session() as session:
            stmt = select(PromptModel).where(
                PromptModel.name.like(f"%{query}%") | PromptModel.description.like(f"%{query}%")
            )
            result = await session.execute(stmt)
            prompts = result.scalars().all()
        return [
            {
                "name": p.name,
                "content": p.content,
                "version": p.version,
                "description": p.description,
                "tags": json.loads(p.tags),
            }
            for p in prompts
        ]

    async def log_roi_stat(self, developer: str, role: str, tokens_saved: float, cost_usd: float, hours_saved: float) -> None:
        async with self.async_session() as session:
            async with session.begin():
                stat = ROIStatModel(
                    stat_id=str(uuid.uuid4()),
                    developer=developer,
                    role=role,
                    tokens_saved=tokens_saved,
                    cost_usd=cost_usd,
                    hours_saved=hours_saved,
                    ts=datetime.now(timezone.utc).isoformat(),
                )
                session.add(stat)

    async def get_roi_stats(self) -> list[dict]:
        async with self.async_session() as session:
            stmt = select(ROIStatModel).order_by(ROIStatModel.ts.desc())
            result = await session.execute(stmt)
            stats = result.scalars().all()
        return [
            {
                "developer": s.developer,
                "role": s.role,
                "tokens_saved": s.tokens_saved,
                "cost_usd": s.cost_usd,
                "hours_saved": s.hours_saved,
                "ts": s.ts,
            }
            for s in stats
        ]

    async def prune(self, retention_weeks: int = 4) -> int:
        from datetime import datetime, timezone, timedelta
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
        return json.dumps([
            {
                "entry_id": e.entry_id,
                "session_id": e.session_id,
                "ts": e.ts,
                "tool": e.tool,
                "summary": e.summary,
                "cost_usd": e.cost_usd,
                "tags": json.loads(e.tags)
            }
            for e in entries
        ], indent=2)

