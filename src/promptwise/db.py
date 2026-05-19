"""SQLite database with async support and migrations."""

import aiosqlite
from pathlib import Path

SCHEMA_VERSION = 2

MIGRATIONS_V1 = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        tool TEXT NOT NULL,
        model TEXT,
        input_tokens INTEGER,
        cached_input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0.0,
        saving_pct REAL DEFAULT 0.0,
        metadata_json TEXT
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_history_ts ON history(ts);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_history_tool ON history(tool);
    """,
]

MIGRATIONS_V2 = [
    "ALTER TABLE history ADD COLUMN duration_ms INTEGER DEFAULT 0;",
    "ALTER TABLE history ADD COLUMN project TEXT;",
    "ALTER TABLE history ADD COLUMN team TEXT;",
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        started_ts TEXT NOT NULL,
        last_ping_ts TEXT NOT NULL,
        metadata_json TEXT
    );
    """,
]


def get_db_path(override: Path | None = None) -> Path:
    """Get the database file path."""
    if override:
        return override
    db_dir = Path.home() / ".promptwise"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "history.db"


async def _apply_v1(db) -> None:
    """Apply v1 migrations if not already applied."""
    await db.execute(MIGRATIONS_V1[0])
    await db.commit()

    cursor = await db.execute(
        "SELECT version FROM schema_version WHERE version = 1"
    )
    already = await cursor.fetchone()
    await cursor.close()

    if already:
        return

    for sql in MIGRATIONS_V1[1:]:
        await db.execute(sql)

    await db.execute(
        "INSERT OR IGNORE INTO schema_version (version) VALUES (1)"
    )
    await db.commit()


async def _apply_v2(db) -> None:
    """Apply v2 migrations if not already applied."""
    cursor = await db.execute(
        "SELECT version FROM schema_version WHERE version = 2"
    )
    already = await cursor.fetchone()
    await cursor.close()

    if already:
        return

    for sql in MIGRATIONS_V2:
        try:
            await db.execute(sql)
        except Exception as exc:
            if "duplicate column name" in str(exc).lower():
                continue  # ALTER TABLE idempotency — column already exists
            raise  # real error (disk full, locked, etc.) — propagate

    await db.execute(
        "INSERT OR IGNORE INTO schema_version (version) VALUES (2)"
    )
    await db.commit()


async def init_db(path: Path | None = None) -> None:
    """Initialize database with all migrations applied idempotently."""
    db_path = get_db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await _apply_v1(db)
        await _apply_v2(db)
