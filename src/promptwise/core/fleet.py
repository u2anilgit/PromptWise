"""core.fleet -- agent fleet governance (WP5). A persistent registry of the
AI agents operating against this repo: role, responsibilities, allowed
tools, budget, owner, and OWASP NHI Top 10 credential metadata (scoped-
credential flag, last-rotation date, JIT-grant linkage by signature).

Raw-sqlite via get_db_path() (~/.promptwise/promptwise.db), same file every
other security/governance store in this codebase uses -- matches
core/jit_permissions.py / security/threat_intel.py's pattern exactly. No
new pip dependency.
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


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class FleetRegistry:
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
                """CREATE TABLE IF NOT EXISTS agent_registry (
                       agent_id             TEXT PRIMARY KEY,
                       role                 TEXT NOT NULL DEFAULT '',
                       responsibilities_json TEXT NOT NULL DEFAULT '[]',
                       allowed_tools_json   TEXT NOT NULL DEFAULT '[]',
                       budget_usd           REAL NOT NULL DEFAULT 0.0,
                       priority             TEXT NOT NULL DEFAULT 'medium',
                       owner                TEXT NOT NULL DEFAULT '',
                       scoped_credential    INTEGER NOT NULL DEFAULT 0,
                       last_rotation_date   TEXT NOT NULL DEFAULT '',
                       jit_grant_signature  TEXT NOT NULL DEFAULT '',
                       registered_at        TEXT NOT NULL,
                       updated_at           TEXT NOT NULL,
                       last_drift_score     REAL NOT NULL DEFAULT 0.0,
                       last_drift_checked_at TEXT NOT NULL DEFAULT ''
                   )""")
            conn.commit()
        finally:
            conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        return {
            "agent_id": row["agent_id"], "role": row["role"],
            "responsibilities": json.loads(row["responsibilities_json"]),
            "allowed_tools": json.loads(row["allowed_tools_json"]),
            "budget_usd": row["budget_usd"], "priority": row["priority"],
            "owner": row["owner"], "scoped_credential": bool(row["scoped_credential"]),
            "last_rotation_date": row["last_rotation_date"],
            "jit_grant_signature": row["jit_grant_signature"],
            "registered_at": row["registered_at"], "updated_at": row["updated_at"],
            "last_drift_score": row["last_drift_score"],
            "last_drift_checked_at": row["last_drift_checked_at"],
        }

    def register(
        self, agent_id: str, *, role: str = "", responsibilities: list[str] | None = None,
        allowed_tools: list[str] | None = None, budget_usd: float = 0.0, priority: str = "medium",
        owner: str = "", scoped_credential: bool = False, last_rotation_date: str = "",
        jit_grant_signature: str = "",
    ) -> dict:
        ts = _now()
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT registered_at FROM agent_registry WHERE agent_id = ?", (agent_id,)).fetchone()
            registered_at = existing["registered_at"] if existing else ts
            conn.execute(
                "INSERT INTO agent_registry (agent_id, role, responsibilities_json, allowed_tools_json, "
                "budget_usd, priority, owner, scoped_credential, last_rotation_date, jit_grant_signature, "
                "registered_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(agent_id) DO UPDATE SET role=excluded.role, "
                "responsibilities_json=excluded.responsibilities_json, "
                "allowed_tools_json=excluded.allowed_tools_json, budget_usd=excluded.budget_usd, "
                "priority=excluded.priority, owner=excluded.owner, "
                "scoped_credential=excluded.scoped_credential, "
                "last_rotation_date=excluded.last_rotation_date, "
                "jit_grant_signature=excluded.jit_grant_signature, updated_at=excluded.updated_at",
                (agent_id, role, json.dumps(responsibilities or []), json.dumps(allowed_tools or []),
                 float(budget_usd), priority, owner, int(bool(scoped_credential)), last_rotation_date,
                 jit_grant_signature, registered_at, ts))
            conn.commit()
            row = conn.execute("SELECT * FROM agent_registry WHERE agent_id = ?", (agent_id,)).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row)

    def get(self, agent_id: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM agent_registry WHERE agent_id = ?", (agent_id,)).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row) if row else None

    def list_all(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM agent_registry ORDER BY agent_id").fetchall()
        finally:
            conn.close()
        return [self._row_to_dict(r) for r in rows]

    def update_drift(self, agent_id: str, score: float, checked_at: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE agent_registry SET last_drift_score = ?, last_drift_checked_at = ? "
                "WHERE agent_id = ?", (float(score), checked_at, agent_id))
            conn.commit()
        finally:
            conn.close()

    def delete(self, agent_id: str) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM agent_registry WHERE agent_id = ?", (agent_id,))
            conn.commit()
        finally:
            conn.close()
