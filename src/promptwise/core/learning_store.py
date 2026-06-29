"""learning_store — durable, searchable corrections (the continuous learning loop).

A correction the user makes ("you used X, it should be Y") becomes a stored, ranked,
replayable rule. Pure stdlib: Python's bundled ``sqlite3`` with an FTS5 virtual table
for BM25 retrieval, and a transparent LIKE fallback when the local SQLite build lacks
FTS5. File-local under ``~/.promptwise/`` — no server, no network, air-gapped safe.

This module is imported lazily by the MCP server's tool dispatch; nothing here runs
unless ``capture_learning`` / ``replay_learnings`` / ``learning_insights`` is called.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path


def default_db_path() -> Path:
    d = Path.home() / ".promptwise"
    d.mkdir(parents=True, exist_ok=True)
    return d / "learning.db"


@dataclass
class Learning:
    id: int
    ts: str
    category: str
    mistake: str
    correction: str
    project: str = ""
    tags: list[str] = field(default_factory=list)
    score: float = 0.0  # retrieval relevance (lower bm25 = better; normalised on return)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "ts": self.ts, "category": self.category,
            "mistake": self.mistake, "correction": self.correction,
            "project": self.project, "tags": self.tags, "score": round(self.score, 4),
        }


class LearningStore:
    """Local SQLite store with FTS5 search and a LIKE fallback."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.fts_enabled = False
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS learnings (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ts TEXT NOT NULL,
                       category TEXT NOT NULL DEFAULT '',
                       mistake TEXT NOT NULL DEFAULT '',
                       correction TEXT NOT NULL DEFAULT '',
                       project TEXT NOT NULL DEFAULT '',
                       tags TEXT NOT NULL DEFAULT '[]'
                   )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_category ON learnings(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_ts ON learnings(ts)")
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS learnings_fts "
                    "USING fts5(category, mistake, correction, project)"
                )
                self.fts_enabled = True
            except sqlite3.OperationalError:
                self.fts_enabled = False  # SQLite built without FTS5 -> LIKE fallback
            conn.commit()
        finally:
            conn.close()

    # ── write ────────────────────────────────────────────────────────────────
    def capture(self, category: str, mistake: str, correction: str,
                project: str = "", tags: list[str] | None = None) -> Learning:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        tags = tags or []
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO learnings (ts, category, mistake, correction, project, tags) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, category or "", mistake or "", correction or "", project or "", json.dumps(tags)),
            )
            rowid = int(cur.lastrowid or 0)
            if self.fts_enabled:
                conn.execute(
                    "INSERT INTO learnings_fts (rowid, category, mistake, correction, project) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (rowid, category or "", mistake or "", correction or "", project or ""),
                )
            conn.commit()
        finally:
            conn.close()
        return Learning(id=rowid, ts=ts, category=category, mistake=mistake,
                        correction=correction, project=project, tags=tags)

    # ── read ─────────────────────────────────────────────────────────────────
    def _row_to_learning(self, row: sqlite3.Row, score: float = 0.0) -> Learning:
        try:
            tags = json.loads(row["tags"])
        except Exception:
            tags = []
        return Learning(id=row["id"], ts=row["ts"], category=row["category"],
                        mistake=row["mistake"], correction=row["correction"],
                        project=row["project"], tags=tags, score=score)

    def search(self, query: str, k: int = 5, project: str | None = None) -> list[Learning]:
        """Top-K relevant past learnings. FTS5 BM25 when available, else LIKE."""
        query = (query or "").strip()
        if not query:
            return self.recent(k=k, project=project)
        if self.fts_enabled:
            try:
                return self._search_fts(query, k, project)
            except sqlite3.OperationalError:
                pass  # malformed MATCH expr -> fall back
        return self._search_like(query, k, project)

    def _search_fts(self, query: str, k: int, project: str | None) -> list[Learning]:
        # Build a safe OR query of bare terms (avoids FTS5 syntax errors on punctuation).
        terms = [t for t in _tokenize(query)]
        if not terms:
            return self._search_like(query, k, project)
        # Prefix queries so 'commit' matches 'committed', 'cred' matches 'credentials'.
        match_expr = " OR ".join(f"{t}*" for t in terms)
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT l.*, bm25(learnings_fts) AS rank "
                "FROM learnings_fts JOIN learnings l ON l.id = learnings_fts.rowid "
                "WHERE learnings_fts MATCH ? ORDER BY rank LIMIT ?",
                (match_expr, k * 4 if project else k),
            ).fetchall()
        finally:
            conn.close()
        out = [self._row_to_learning(r, score=float(r["rank"])) for r in rows]
        if project:
            out = [l for l in out if l.project == project][:k]
        return out[:k]

    def _search_like(self, query: str, k: int, project: str | None) -> list[Learning]:
        terms = _tokenize(query)
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM learnings ORDER BY ts DESC").fetchall()
        finally:
            conn.close()
        scored = []
        for r in rows:
            if project and r["project"] != project:
                continue
            hay = f"{r['category']} {r['mistake']} {r['correction']} {r['project']}".lower()
            hits = sum(1 for t in terms if t in hay)
            if hits:
                # negative so that ORDER-like (lower better) stays consistent with bm25
                scored.append((-(float(hits)), self._row_to_learning(r, score=-float(hits))))
        scored.sort(key=lambda x: x[0])
        return [l for _, l in scored[:k]]

    def recent(self, k: int = 5, project: str | None = None) -> list[Learning]:
        conn = self._connect()
        try:
            if project:
                rows = conn.execute(
                    "SELECT * FROM learnings WHERE project = ? ORDER BY ts DESC LIMIT ?",
                    (project, k)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM learnings ORDER BY ts DESC LIMIT ?", (k,)).fetchall()
        finally:
            conn.close()
        return [self._row_to_learning(r) for r in rows]

    def all(self) -> list[Learning]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM learnings ORDER BY ts").fetchall()
        finally:
            conn.close()
        return [self._row_to_learning(r) for r in rows]

    def count(self) -> int:
        conn = self._connect()
        try:
            return int(conn.execute("SELECT COUNT(*) AS c FROM learnings").fetchone()["c"])
        finally:
            conn.close()


def _tokenize(text: str) -> list[str]:
    import re
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if len(t) > 1]
