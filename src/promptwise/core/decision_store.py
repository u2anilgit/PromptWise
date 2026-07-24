"""decision_store -- lightweight ADR (Architecture Decision Record) log.

Mirrors security/risk_register.py's pattern: sync stdlib sqlite, same local
db (get_db_path()), additive table. Captures *why* a decision was made --
context, decision, consequences -- queryable by keyword/tag/status, so it
survives beyond a commit message or a chat transcript.

No approval workflow, no auto-extraction from commits/PRs: record_decision
is a single trusted call, same trust model as security/risk_register.py's
accept_risk.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path


def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


class DecisionStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else _default_db()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS decisions (
                       id            INTEGER PRIMARY KEY AUTOINCREMENT,
                       title         TEXT NOT NULL,
                       status        TEXT NOT NULL DEFAULT 'accepted',
                       context       TEXT NOT NULL,
                       decision      TEXT NOT NULL,
                       consequences  TEXT NOT NULL DEFAULT '',
                       tags          TEXT NOT NULL DEFAULT '',
                       created_at    TEXT NOT NULL,
                       superseded_by INTEGER
                   )""")
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        title: str,
        context: str,
        decision: str,
        consequences: str = "",
        tags: str = "",
        status: str = "accepted",
        supersedes: int | None = None,
        ts: str | None = None,
    ) -> int:
        ts = ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO decisions "
                "(title, status, context, decision, consequences, tags, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, status, context, decision, consequences, tags, ts))
            new_id = cur.lastrowid
            assert new_id is not None
            if supersedes is not None:
                conn.execute(
                    "UPDATE decisions SET status = 'superseded', superseded_by = ? WHERE id = ?",
                    (new_id, supersedes))
            conn.commit()
        finally:
            conn.close()
        return int(new_id)

    def get(self, id: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM decisions WHERE id = ?", (id,)).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def _tag_matches(self, stored_tags: str, tag: str) -> bool:
        parts = {t.strip() for t in stored_tags.split(",") if t.strip()}
        return tag in parts

    def list(self, status: str | None = None, tag: str | None = None) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM decisions ORDER BY created_at DESC").fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            d = dict(r)
            if status is not None and d["status"] != status:
                continue
            if tag is not None and not self._tag_matches(d["tags"], tag):
                continue
            out.append(d)
        return out

    def search(self, query: str) -> list[dict]:
        if not query:
            return []
        needle = query.lower()
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM decisions ORDER BY created_at DESC").fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            d = dict(r)
            haystack = " ".join([d["title"], d["context"], d["decision"], d["consequences"]]).lower()
            if needle in haystack:
                out.append(d)
        return out
