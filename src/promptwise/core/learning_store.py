"""learning_store — durable, searchable corrections (the continuous learning loop).

A correction the user makes ("you used X, it should be Y") becomes a stored, ranked,
replayable rule. Pure stdlib: Python's bundled ``sqlite3`` with an FTS5 virtual table
for BM25 retrieval, and a transparent LIKE fallback when the local SQLite build lacks
FTS5. File-local under ``~/.promptwise/`` — no server, no network, air-gapped safe.

This module is imported lazily by the MCP server's tool dispatch; nothing here runs
unless ``capture_learning`` / ``replay_learnings`` / ``learning_insights`` is called.

Fact supersession (Phase 19 / candidate D1, no new dependency): passing
``supersedes=<id>`` to ``capture()`` atomically marks the prior learning
``status='superseded'`` in the same write, mirroring ``decision_store.py``'s
``supersedes`` param. ``search()``/``recent()`` exclude superseded entries by
default (a corrected fact no longer competes with its own correction for
retrieval); ``all()`` keeps returning full history unchanged, since
``insights.py`` uses it for trend analysis where the historical record —
including what got corrected away — is the point.
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
    status: str = "active"
    superseded_by: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "ts": self.ts, "category": self.category,
            "mistake": self.mistake, "correction": self.correction,
            "project": self.project, "tags": self.tags, "score": round(self.score, 4),
            "status": self.status, "superseded_by": self.superseded_by,
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
            self._ensure_supersession_columns(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_category ON learnings(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_ts ON learnings(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_status ON learnings(status)")
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

    def _ensure_supersession_columns(self, conn: sqlite3.Connection) -> None:
        """Existing DBs predate status/superseded_by -- add them if absent.
        Nullable/defaulted, no backfill, no data loss (same pattern as
        db/models.py's _ensure_cost_logs_project_id)."""
        cols = [row[1] for row in conn.execute("PRAGMA table_info(learnings)").fetchall()]
        if "status" not in cols:
            conn.execute("ALTER TABLE learnings ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        if "superseded_by" not in cols:
            conn.execute("ALTER TABLE learnings ADD COLUMN superseded_by INTEGER")

    # ── write ────────────────────────────────────────────────────────────────
    def capture(self, category: str, mistake: str, correction: str,
                project: str = "", tags: list[str] | None = None,
                supersedes: int | None = None) -> Learning:
        """Store a correction. ``supersedes=<id>`` atomically marks that prior
        learning superseded (status + superseded_by) in the same write --
        it stops being returned by search()/recent() but is never deleted."""
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
            if supersedes is not None:
                conn.execute(
                    "UPDATE learnings SET status = 'superseded', superseded_by = ? WHERE id = ?",
                    (rowid, supersedes),
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
        keys = row.keys()
        status = row["status"] if "status" in keys else "active"
        superseded_by = row["superseded_by"] if "superseded_by" in keys else None
        return Learning(id=row["id"], ts=row["ts"], category=row["category"],
                        mistake=row["mistake"], correction=row["correction"],
                        project=row["project"], tags=tags, score=score,
                        status=status or "active", superseded_by=superseded_by)

    def search(self, query: str, k: int = 5, project: str | None = None,
               include_superseded: bool = False) -> list[Learning]:
        """Top-K relevant past learnings. FTS5 BM25 when available, else LIKE.
        Superseded learnings are excluded by default -- a corrected-away fact
        shouldn't compete with (or be mistaken for) its own correction."""
        query = (query or "").strip()
        if not query:
            return self.recent(k=k, project=project, include_superseded=include_superseded)
        if self.fts_enabled:
            try:
                return self._search_fts(query, k, project, include_superseded)
            except sqlite3.OperationalError:
                pass  # malformed MATCH expr -> fall back
        return self._search_like(query, k, project, include_superseded)

    def _search_fts(self, query: str, k: int, project: str | None,
                     include_superseded: bool = False) -> list[Learning]:
        # Build a safe OR query of bare terms (avoids FTS5 syntax errors on punctuation).
        terms = [t for t in _tokenize(query)]
        if not terms:
            return self._search_like(query, k, project, include_superseded)
        # Prefix queries so 'commit' matches 'committed', 'cred' matches 'credentials'.
        match_expr = " OR ".join(f"{t}*" for t in terms)
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT l.*, bm25(learnings_fts) AS rank "
                "FROM learnings_fts JOIN learnings l ON l.id = learnings_fts.rowid "
                "WHERE learnings_fts MATCH ? ORDER BY rank LIMIT ?",
                (match_expr, k * 4 if (project or not include_superseded) else k),
            ).fetchall()
        finally:
            conn.close()
        out = [self._row_to_learning(r, score=float(r["rank"])) for r in rows]
        if not include_superseded:
            out = [l for l in out if l.status != "superseded"]
        if project:
            out = [l for l in out if l.project == project]
        return out[:k]

    def _search_like(self, query: str, k: int, project: str | None,
                      include_superseded: bool = False) -> list[Learning]:
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
            learning = self._row_to_learning(r)
            if not include_superseded and learning.status == "superseded":
                continue
            hay = f"{r['category']} {r['mistake']} {r['correction']} {r['project']}".lower()
            hits = sum(1 for t in terms if t in hay)
            if hits:
                # negative so that ORDER-like (lower better) stays consistent with bm25
                learning.score = -float(hits)
                scored.append((-(float(hits)), learning))
        scored.sort(key=lambda x: x[0])
        return [l for _, l in scored[:k]]

    def recent(self, k: int = 5, project: str | None = None,
               include_superseded: bool = False) -> list[Learning]:
        conn = self._connect()
        try:
            if project:
                rows = conn.execute(
                    "SELECT * FROM learnings WHERE project = ? ORDER BY ts DESC",
                    (project,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM learnings ORDER BY ts DESC").fetchall()
        finally:
            conn.close()
        out = [self._row_to_learning(r) for r in rows]
        if not include_superseded:
            out = [l for l in out if l.status != "superseded"]
        return out[:k]

    def all(self) -> list[Learning]:
        """Full history, superseded entries included -- insights.py's trend
        analysis wants the historical record, not just what's still active."""
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
