"""incidents -- incident lifecycle with an enforced status-transition graph.
open -> triaged -> contained -> resolved -> closed, linear only, no
skipping and no going back. This is the first multi-state enforced
transition graph in this codebase (core/approvals.py's Approvals and
core/learning_store.py's LearningStore are both one-hop status flips, not
a graph) -- the guard shape below generalizes approvals.py's single
`if current_status != "pending": raise` check into a graph lookup.

Same small-sqlite-store pattern as core/approvals.py: sync stdlib sqlite3
via the shared get_db_path() resolver, additive tables.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"triaged"},
    "triaged": {"contained"},
    "contained": {"resolved"},
    "resolved": {"closed"},
    "closed": set(),
}


def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        return Path.home() / ".promptwise" / "promptwise.db"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class Incident:
    id: int
    title: str
    severity: str
    status: str
    created_at: str
    updated_at: str
    description: str = ""
    aivss_score: float | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IncidentEvent:
    id: int
    incident_id: int
    event_type: str
    detail: str
    actor: str
    ts: str

    def to_dict(self) -> dict:
        return asdict(self)


class IncidentStore:
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
                """CREATE TABLE IF NOT EXISTS incidents (
                       id           INTEGER PRIMARY KEY AUTOINCREMENT,
                       title        TEXT NOT NULL,
                       description  TEXT NOT NULL DEFAULT '',
                       severity     TEXT NOT NULL DEFAULT 'unknown',
                       status       TEXT NOT NULL DEFAULT 'open',
                       aivss_score  REAL,
                       metadata_json TEXT NOT NULL DEFAULT '{}',
                       created_at   TEXT NOT NULL,
                       updated_at   TEXT NOT NULL
                   )""")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS incident_events (
                       id           INTEGER PRIMARY KEY AUTOINCREMENT,
                       incident_id  INTEGER NOT NULL,
                       event_type   TEXT NOT NULL,
                       detail       TEXT NOT NULL DEFAULT '',
                       actor        TEXT NOT NULL DEFAULT '',
                       ts           TEXT NOT NULL
                   )""")
            conn.commit()
        finally:
            conn.close()

    def _row_to_incident(self, row: sqlite3.Row) -> Incident:
        return Incident(
            id=row["id"], title=row["title"], description=row["description"],
            severity=row["severity"], status=row["status"],
            aivss_score=row["aivss_score"], metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"], updated_at=row["updated_at"])

    def create(self, title: str, description: str = "", severity: str = "unknown",
               metadata: dict | None = None) -> Incident:
        now = _now()
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO incidents (title, description, severity, status, "
                "metadata_json, created_at, updated_at) VALUES (?, ?, ?, 'open', ?, ?, ?)",
                (title, description, severity, json.dumps(metadata or {}), now, now))
            conn.commit()
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (cur.lastrowid,)).fetchone()
        finally:
            conn.close()
        return self._row_to_incident(row)

    def update_status(self, incident_id: int, new_status: str, actor: str = "") -> Incident:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            if row is None:
                raise ValueError(f"no incident with id {incident_id}")
            current_status = row["status"]
            allowed = _ALLOWED_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise ValueError(
                    f"illegal transition: incident {incident_id} is '{current_status}', "
                    f"cannot move to '{new_status}' (allowed: {sorted(allowed) or 'none'})")
            now = _now()
            conn.execute(
                "UPDATE incidents SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, incident_id))
            conn.commit()
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        finally:
            conn.close()
        inc = self._row_to_incident(row)
        self.add_event(incident_id, "status_change", f"{current_status} -> {new_status}", actor=actor)
        return inc

    def set_score(self, incident_id: int, aivss_score: float) -> Incident:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            if row is None:
                raise ValueError(f"no incident with id {incident_id}")
            conn.execute("UPDATE incidents SET aivss_score = ?, updated_at = ? WHERE id = ?",
                         (aivss_score, _now(), incident_id))
            conn.commit()
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        finally:
            conn.close()
        return self._row_to_incident(row)

    def get(self, incident_id: int) -> Incident | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        finally:
            conn.close()
        return self._row_to_incident(row) if row else None

    def list_all(self, status: str | None = None) -> list[Incident]:
        conn = self._connect()
        try:
            if status:
                rows = conn.execute("SELECT * FROM incidents WHERE status = ?", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM incidents").fetchall()
        finally:
            conn.close()
        return [self._row_to_incident(r) for r in rows]

    def add_event(self, incident_id: int, event_type: str, detail: str, actor: str = "") -> IncidentEvent:
        now = _now()
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO incident_events (incident_id, event_type, detail, actor, ts) "
                "VALUES (?, ?, ?, ?, ?)", (incident_id, event_type, detail, actor, now))
            conn.commit()
            row = conn.execute("SELECT * FROM incident_events WHERE id = ?", (cur.lastrowid,)).fetchone()
        finally:
            conn.close()
        return IncidentEvent(id=row["id"], incident_id=row["incident_id"], event_type=row["event_type"],
                              detail=row["detail"], actor=row["actor"], ts=row["ts"])

    def list_events(self, incident_id: int) -> list[IncidentEvent]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM incident_events WHERE incident_id = ? ORDER BY ts ASC",
                (incident_id,)).fetchall()
        finally:
            conn.close()
        return [IncidentEvent(id=r["id"], incident_id=r["incident_id"], event_type=r["event_type"],
                               detail=r["detail"], actor=r["actor"], ts=r["ts"]) for r in rows]
