"""Session lifecycle tracking for timeout detection."""

import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import aiosqlite

from promptwise.db import get_db_path
from promptwise.types import SessionPingResult, TimeoutCheckResult


class SessionManager:
    """Track session activity for timeout detection."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = get_db_path(db_path)

    async def ping(self, session_id: Optional[str] = None) -> SessionPingResult:
        """Record session activity. Creates session if session_id is None or unknown."""
        now = datetime.now(timezone.utc).isoformat()
        is_new = session_id is None

        if is_new:
            session_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if is_new:
                await db.execute(
                    "INSERT INTO sessions (session_id, started_ts, last_ping_ts) VALUES (?, ?, ?)",
                    (session_id, now, now),
                )
                await db.commit()
                return SessionPingResult(
                    session_id=session_id,
                    started_ts=now,
                    last_ping_ts=now,
                    is_new=True,
                )

            cursor = await db.execute(
                "SELECT started_ts FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()

            if row is None:
                await db.execute(
                    "INSERT INTO sessions (session_id, started_ts, last_ping_ts) VALUES (?, ?, ?)",
                    (session_id, now, now),
                )
                await db.commit()
                return SessionPingResult(
                    session_id=session_id,
                    started_ts=now,
                    last_ping_ts=now,
                    is_new=True,
                )

            started_ts = row["started_ts"]
            await db.execute(
                "UPDATE sessions SET last_ping_ts = ? WHERE session_id = ?",
                (now, session_id),
            )
            await db.commit()
            return SessionPingResult(
                session_id=session_id,
                started_ts=started_ts,
                last_ping_ts=now,
                is_new=False,
            )

    async def check_timeout(
        self,
        session_id: str,
        idle_threshold_minutes: int = 30,
        warn_threshold_minutes: int = 20,
    ) -> TimeoutCheckResult:
        """Check if session has exceeded idle thresholds."""
        now = datetime.now(timezone.utc)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT last_ping_ts FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()

        if row is None:
            return TimeoutCheckResult(
                session_id=session_id,
                status="active",
                idle_minutes=0.0,
                recommended_action="continue",
                message="Session not found; treating as active.",
            )

        last_ping = datetime.fromisoformat(row["last_ping_ts"])
        if last_ping.tzinfo is None:
            last_ping = last_ping.replace(tzinfo=timezone.utc)

        idle_minutes = (now - last_ping).total_seconds() / 60

        if idle_minutes >= idle_threshold_minutes:
            return TimeoutCheckResult(
                session_id=session_id,
                status="expired",
                idle_minutes=round(idle_minutes, 1),
                recommended_action="summarize_thread",
                message=(
                    f"Session idle {idle_minutes:.1f} min "
                    f"(threshold: {idle_threshold_minutes} min). "
                    "Call summarize_thread then suggest /clear."
                ),
            )

        if idle_minutes >= warn_threshold_minutes:
            remaining = idle_threshold_minutes - idle_minutes
            return TimeoutCheckResult(
                session_id=session_id,
                status="warn",
                idle_minutes=round(idle_minutes, 1),
                recommended_action="prompt_user",
                message=(
                    f"Session idle {idle_minutes:.1f} min. "
                    f"Ask user if still active — closes in {remaining:.1f} min."
                ),
            )

        return TimeoutCheckResult(
            session_id=session_id,
            status="active",
            idle_minutes=round(idle_minutes, 1),
            recommended_action="continue",
            message="Session active.",
        )
