"""Append-only history of injection-corpus promotions.

Mirrors risk_register.py's pattern: sync stdlib sqlite, same local db
(get_db_path()), additive table. Unlike RiskRegister.upsert(), every
call is a plain INSERT -- history rows are never updated, only added.
"""
from __future__ import annotations

import json
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


class CorpusStore:
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
                """CREATE TABLE IF NOT EXISTS corpus_history (
                       id              INTEGER PRIMARY KEY AUTOINCREMENT,
                       action          TEXT NOT NULL,
                       reviewer        TEXT NOT NULL,
                       candidate_path  TEXT NOT NULL,
                       approved_ids    TEXT NOT NULL,
                       rejected_ids    TEXT NOT NULL,
                       before_json     TEXT NOT NULL,
                       after_json      TEXT NOT NULL,
                       created_at      TEXT NOT NULL
                   )"""
            )
            conn.commit()
        finally:
            conn.close()

    def append_history(
        self,
        action: str,
        reviewer: str,
        candidate_path: str,
        approved_ids: list[str],
        rejected_ids: list[str],
        before: dict,
        after: dict,
    ) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO corpus_history
                       (action, reviewer, candidate_path, approved_ids,
                        rejected_ids, before_json, after_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    action,
                    reviewer,
                    candidate_path,
                    json.dumps(approved_ids),
                    json.dumps(rejected_ids),
                    json.dumps(before),
                    json.dumps(after),
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_history(self, limit: int = 50) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM corpus_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "action": r["action"],
                    "reviewer": r["reviewer"],
                    "candidate_path": r["candidate_path"],
                    "approved_ids": json.loads(r["approved_ids"]),
                    "rejected_ids": json.loads(r["rejected_ids"]),
                    "before": json.loads(r["before_json"]),
                    "after": json.loads(r["after_json"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()
