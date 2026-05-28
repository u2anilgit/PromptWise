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
CREATE INDEX IF NOT EXISTS idx_mem_ts ON memory_entries(ts);
