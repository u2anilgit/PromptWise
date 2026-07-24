"""routing_consent -- device-scoped, ask-once consent flags for the assistant
to check before repeatedly asking the same routing question (e.g. "use Opus
for this?"). Mirrors security/risk_register.py's established small-sqlite-
store pattern: sync stdlib sqlite via the shared get_db_path() resolver
(same ~/.promptwise/promptwise.db every other device-scoped feature uses),
additive table.

Not consulted by Router.route() -- routing itself stays silent/automatic as
it always has. This module only backs the assistant's own "ask once per
device, then remember" behavior; it has no effect on tier selection.
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


class RoutingConsent:
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
                """CREATE TABLE IF NOT EXISTS routing_consent (
                       key        TEXT PRIMARY KEY,
                       granted    INTEGER NOT NULL DEFAULT 0,
                       granted_at TEXT
                   )""")
            conn.commit()
        finally:
            conn.close()

    def grant(self, key: str) -> None:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO routing_consent (key, granted, granted_at) VALUES (?, 1, ?) "
                "ON CONFLICT(key) DO UPDATE SET granted = 1, granted_at = excluded.granted_at",
                (key, ts))
            conn.commit()
        finally:
            conn.close()

    def revoke(self, key: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO routing_consent (key, granted, granted_at) VALUES (?, 0, NULL) "
                "ON CONFLICT(key) DO UPDATE SET granted = 0, granted_at = NULL",
                (key,))
            conn.commit()
        finally:
            conn.close()

    def is_granted(self, key: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT granted FROM routing_consent WHERE key = ?", (key,)).fetchone()
        finally:
            conn.close()
        return bool(row and row["granted"])
