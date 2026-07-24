"""jit_permissions -- time-boxed, tool-signature-scoped permission grants.

A grant is temporary: "allow this tool for the next N minutes," then
auto-reverts to normal prompting once the window lapses. Same small-sqlite-
store pattern as core/routing_consent.py: sync stdlib sqlite via the shared
get_db_path() resolver (~/.promptwise/promptwise.db, same db every other
device-scoped feature uses), additive table.

Does not touch .mcp.json -- that file's alwaysAllow has no TTL concept in
Claude Code itself. This store is a parallel, additive layer enforced by
hooks/pretooluse_jit_guard.py at PreToolUse time. Signature grain matches
permission_tuner._command_signature (e.g. "Bash:git",
"mcp__promptwise__run_governor").
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

_MIN_TTL_MINUTES = 1
_MAX_TTL_MINUTES = 480  # 8h
_DEFAULT_TTL_MINUTES = 60


def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


def _now() -> float:
    return time.time()


def _fmt(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _parse(ts: str) -> float:
    return time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone


class JITPermissions:
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
                """CREATE TABLE IF NOT EXISTS jit_permissions (
                       signature  TEXT PRIMARY KEY,
                       granted_at TEXT NOT NULL,
                       expires_at TEXT NOT NULL
                   )""")
            conn.commit()
        finally:
            conn.close()

    def grant(self, signature: str, ttl_minutes: int = _DEFAULT_TTL_MINUTES) -> dict:
        ttl = max(_MIN_TTL_MINUTES, min(_MAX_TTL_MINUTES, int(ttl_minutes)))
        now = _now()
        granted_at = _fmt(now)
        expires_at = _fmt(now + ttl * 60)
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO jit_permissions (signature, granted_at, expires_at) VALUES (?, ?, ?) "
                "ON CONFLICT(signature) DO UPDATE SET granted_at = excluded.granted_at, "
                "expires_at = excluded.expires_at",
                (signature, granted_at, expires_at))
            conn.commit()
        finally:
            conn.close()
        return {"signature": signature, "granted_at": granted_at, "expires_at": expires_at}

    def revoke(self, signature: str) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM jit_permissions WHERE signature = ?", (signature,))
            conn.commit()
        finally:
            conn.close()

    def is_active(self, signature: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT expires_at FROM jit_permissions WHERE signature = ?", (signature,)).fetchone()
        finally:
            conn.close()
        if not row:
            return False
        return _parse(row["expires_at"]) > _now()

    def has_record(self, signature: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM jit_permissions WHERE signature = ?", (signature,)).fetchone()
        finally:
            conn.close()
        return row is not None

    def list_all(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT signature, granted_at, expires_at FROM jit_permissions "
                "ORDER BY granted_at DESC").fetchall()
        finally:
            conn.close()
        now = _now()
        out = []
        for r in rows:
            status = "active" if _parse(r["expires_at"]) > now else "expired"
            out.append({"signature": r["signature"], "granted_at": r["granted_at"],
                        "expires_at": r["expires_at"], "status": status})
        return out
