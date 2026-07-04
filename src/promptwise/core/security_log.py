"""security_log — durable, offline record of run_security_suite verdicts.

Mirrors ``eval_harness.EvalResultStore``: sync stdlib sqlite, same local db
(``get_db_path()``), additive table so ``insights_report`` and the red-team
harness can read historical security-suite runs. Prior to this module,
``run_security_suite`` results were ephemeral (returned as JSON, never saved).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path


def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


class SecurityScanStore:
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
                """CREATE TABLE IF NOT EXISTS security_scan_results (
                       scan_id TEXT PRIMARY KEY,
                       ts TEXT NOT NULL,
                       checks_run TEXT NOT NULL DEFAULT '[]',
                       findings_count INTEGER NOT NULL DEFAULT 0,
                       severity_breakdown TEXT NOT NULL DEFAULT '{}',
                       passed INTEGER NOT NULL DEFAULT 1
                   )""")
            conn.commit()
        finally:
            conn.close()

    def record(self, *, checks_run: list[str], findings_count: int,
               severity_breakdown: dict, passed: bool, ts: str | None = None) -> str:
        scan_id = uuid.uuid4().hex
        ts = ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO security_scan_results "
                "(scan_id, ts, checks_run, findings_count, severity_breakdown, passed) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (scan_id, ts, json.dumps(list(checks_run)), int(findings_count),
                 json.dumps(severity_breakdown), 1 if passed else 0))
            conn.commit()
        finally:
            conn.close()
        return scan_id

    def results(self, limit: int = 100) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM security_scan_results ORDER BY ts DESC LIMIT ?",
                (limit,)).fetchall()
        finally:
            conn.close()
        return [{"scan_id": r["scan_id"], "ts": r["ts"],
                 "checks_run": json.loads(r["checks_run"]),
                 "findings_count": r["findings_count"],
                 "severity_breakdown": json.loads(r["severity_breakdown"]),
                 "passed": bool(r["passed"])} for r in rows]
