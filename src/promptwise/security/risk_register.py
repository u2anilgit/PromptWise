"""risk_register -- individual security findings tracked over time with
self-service accept/expire sign-off.

Mirrors ``core/security_log.py``'s pattern: sync stdlib sqlite, same local
db (``get_db_path()``), additive table. Unlike ``SecurityScanStore`` (which
records whole scan runs), this tracks INDIVIDUAL findings with a stable
identity across repeated scans, so accepting one known risk doesn't silence
an entire scan.

Self-service by design: ``accept()`` is one call, no approval workflow.
Expiry is computed lazily at read-time (``status_of``/``list``/``summary``)
-- no background job or scheduled review ever mutates a row. A finding
that stops appearing in scans is never auto-resolved (see the design doc's
explicit non-goal): this module only ever upserts on observation.
"""
from __future__ import annotations

import hashlib
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


def fingerprint(check: str, detail: str) -> str:
    """Stable identity for a finding: same check+detail always hashes the
    same, across any number of repeated scans."""
    return hashlib.sha256(f"{check}:{detail}".encode("utf-8")).hexdigest()[:16]


class RiskRegister:
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
                """CREATE TABLE IF NOT EXISTS risk_register (
                       fingerprint TEXT PRIMARY KEY,
                       check_name  TEXT NOT NULL,
                       detail      TEXT NOT NULL,
                       first_seen  TEXT NOT NULL,
                       last_seen   TEXT NOT NULL,
                       status      TEXT NOT NULL DEFAULT 'open',
                       accepted_by TEXT,
                       accepted_reason TEXT,
                       accepted_at TEXT,
                       expires_at  TEXT
                   )""")
            conn.commit()
        finally:
            conn.close()

    def upsert(self, check: str, detail: str, ts: str | None = None) -> str:
        fp = fingerprint(check, detail)
        ts = ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT fingerprint FROM risk_register WHERE fingerprint = ?", (fp,)).fetchone()
            if existing:
                conn.execute("UPDATE risk_register SET last_seen = ? WHERE fingerprint = ?", (ts, fp))
            else:
                conn.execute(
                    "INSERT INTO risk_register "
                    "(fingerprint, check_name, detail, first_seen, last_seen, status) "
                    "VALUES (?, ?, ?, ?, ?, 'open')",
                    (fp, check, detail, ts, ts))
            conn.commit()
        finally:
            conn.close()
        return fp

    def accept(self, fp: str, reason: str, expires_at: str | None = None, accepted_by: str = "") -> bool:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT fingerprint FROM risk_register WHERE fingerprint = ?", (fp,)).fetchone()
            if not existing:
                return False
            conn.execute(
                "UPDATE risk_register SET status = 'accepted', accepted_by = ?, "
                "accepted_reason = ?, accepted_at = ?, expires_at = ? WHERE fingerprint = ?",
                (accepted_by, reason, ts, expires_at, fp))
            conn.commit()
        finally:
            conn.close()
        return True

    def _computed_status(self, row: sqlite3.Row, now_iso: str) -> str:
        if row["status"] == "accepted" and row["expires_at"] and row["expires_at"] < now_iso:
            return "expired"
        return row["status"]

    def status_of(self, fp: str, *, now_iso: str | None = None) -> str:
        now_iso = now_iso or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM risk_register WHERE fingerprint = ?", (fp,)).fetchone()
        finally:
            conn.close()
        if not row:
            return "open"
        return self._computed_status(row, now_iso)

    def list(self, status: str | None = None, *, now_iso: str | None = None) -> list[dict]:
        now_iso = now_iso or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM risk_register ORDER BY last_seen DESC").fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            computed = self._computed_status(r, now_iso)
            if status is not None and computed != status:
                continue
            out.append({
                "fingerprint": r["fingerprint"], "check": r["check_name"], "detail": r["detail"],
                "first_seen": r["first_seen"], "last_seen": r["last_seen"], "status": computed,
                "accepted_by": r["accepted_by"], "accepted_reason": r["accepted_reason"],
                "accepted_at": r["accepted_at"], "expires_at": r["expires_at"],
            })
        return out

    def summary(self, *, now_iso: str | None = None) -> dict:
        now_iso = now_iso or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        counts = {"open": 0, "accepted": 0, "expired": 0}
        for row in self.list(now_iso=now_iso):
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return counts
