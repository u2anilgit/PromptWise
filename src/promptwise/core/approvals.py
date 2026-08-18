"""approvals -- pending-approval workflow for policy-escalated actions.

An `escalate`-mode policy violation becomes a pending row here instead of
a hard block (see core/policy.py's `enforcement` field). A human (or a
governor) resolves it: approve mints a scoped, time-boxed JIT grant by
calling the existing JITPermissions.grant() -- no new grant mechanism,
this reuses the one core/jit_permissions.py already has -- deny leaves
the action blocked. Same small-sqlite-store pattern as
core/jit_permissions.py / core/decision_store.py: sync stdlib sqlite via
the shared get_db_path() resolver, additive table.

The full chain (who requested, who resolved, when, what grant resulted)
is reconstructable from one row -- see test_approval_chain_reconstructable
_from_record for the guarantee this module makes.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

_DECISIONS = ("approved", "denied")
_DEFAULT_TTL_MINUTES = 60


def _default_db() -> Path:
    from promptwise.db.models import get_db_path
    return get_db_path()


def _now() -> float:
    return time.time()


def _fmt(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class Approvals:
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
                """CREATE TABLE IF NOT EXISTS approvals (
                       id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                       created_at             TEXT NOT NULL,
                       requester              TEXT NOT NULL,
                       action_signature       TEXT NOT NULL,
                       context_json           TEXT NOT NULL,
                       status                 TEXT NOT NULL,
                       resolver               TEXT,
                       resolved_at            TEXT,
                       ttl_minutes            INTEGER NOT NULL,
                       resulting_jit_signature TEXT
                   )""")
            conn.commit()
        finally:
            conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "requester": row["requester"],
            "action_signature": row["action_signature"],
            "context": json.loads(row["context_json"]),
            "status": row["status"],
            "resolver": row["resolver"],
            "resolved_at": row["resolved_at"],
            "ttl_minutes": row["ttl_minutes"],
            "resulting_jit_signature": row["resulting_jit_signature"],
        }

    def request(self, requester: str, action_signature: str, context: dict,
                ttl_minutes: int = _DEFAULT_TTL_MINUTES) -> dict:
        created_at = _fmt(_now())
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO approvals (created_at, requester, action_signature, "
                "context_json, status, ttl_minutes) VALUES (?, ?, ?, ?, 'pending', ?)",
                (created_at, requester, action_signature, json.dumps(context or {}),
                 int(ttl_minutes)))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (cur.lastrowid,)).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row)

    def resolve(self, approval_id: int, resolver: str, decision: str,
                jit_ttl_minutes: int | None = None, jit_store=None) -> dict:
        if decision not in _DECISIONS:
            raise ValueError(f"approval decision '{decision}' not one of {_DECISIONS}")
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            if row is None:
                raise ValueError(f"no approval with id {approval_id}")
            current = self._row_to_dict(row)

            resulting_signature = None
            if decision == "approved":
                if jit_store is None:
                    from promptwise.core.jit_permissions import JITPermissions
                    jit_store = JITPermissions(self.db_path)
                jit_store.grant(
                    current["action_signature"],
                    ttl_minutes=jit_ttl_minutes or current["ttl_minutes"])
                resulting_signature = current["action_signature"]

            resolved_at = _fmt(_now())
            conn.execute(
                "UPDATE approvals SET status = ?, resolver = ?, resolved_at = ?, "
                "resulting_jit_signature = ? WHERE id = ?",
                (decision, resolver, resolved_at, resulting_signature, approval_id))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row)

    def list_pending(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status = 'pending' "
                "ORDER BY created_at ASC").fetchall()
        finally:
            conn.close()
        now = _now()
        out = []
        for r in rows:
            d = self._row_to_dict(r)
            created = time.strptime(d["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            import calendar
            created_epoch = calendar.timegm(created)
            d["age_minutes"] = round((now - created_epoch) / 60, 1)
            d["expires_in_minutes"] = round(
                (created_epoch + d["ttl_minutes"] * 60 - now) / 60, 1)
            out.append(d)
        return out

    def get(self, approval_id: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row) if row else None
