import aiosqlite
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from promptwise_v2.types_v2 import MemoryEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_entries (
    entry_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    tool TEXT NOT NULL,
    summary TEXT NOT NULL,
    cost_usd REAL DEFAULT 0.0,
    tags TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_mem_session ON memory_entries(session_id);
"""


class MemoryManager:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()

    async def log(self, *, session_id: str, tool: str, summary: str,
                  cost_usd: float = 0.0, tags: list[str] | None = None) -> MemoryEntry:
        entry_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags or [])
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO memory_entries VALUES (?,?,?,?,?,?,?)",
                (entry_id, session_id, ts, tool, summary, cost_usd, tags_json),
            )
            await db.commit()
        return MemoryEntry(entry_id=entry_id, session_id=session_id, ts=ts,
                           tool=tool, summary=summary, cost_usd=cost_usd,
                           tags=tags or [])

    async def get_context(self, session_id: str, limit: int = 20) -> list[MemoryEntry]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM memory_entries WHERE session_id=? ORDER BY ts DESC LIMIT ?",
                (session_id, limit),
            ) as cur:
                rows = await cur.fetchall()
        return [
            MemoryEntry(entry_id=r["entry_id"], session_id=r["session_id"],
                        ts=r["ts"], tool=r["tool"], summary=r["summary"],
                        cost_usd=r["cost_usd"], tags=json.loads(r["tags"]))
            for r in rows
        ]

    async def prune(self, retention_weeks: int = 4) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(weeks=retention_weeks)).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute("DELETE FROM memory_entries WHERE ts < ?", (cutoff,))
            await db.commit()
            return cur.rowcount

    async def export_json(self) -> str:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM memory_entries ORDER BY ts") as cur:
                rows = await cur.fetchall()
        return json.dumps([dict(r) for r in rows], indent=2)
