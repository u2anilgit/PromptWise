"""effort_adapter -- reasoning-effort selection that learns from its own
outcome history, structurally mirroring adaptive_router.py's OutcomeStore /
AdaptiveRouter but over the EFFORT_ORDER ladder (low -> medium -> high)
instead of the model-tier ladder. Same design contract: additive, fail-open,
bounded/stable (Beta-style posterior + minimum-sample threshold), absence is
neutral never negative, offline/stdlib-only.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from promptwise.core.adaptive_router import normalize_quality_signal
from promptwise.core.effort_router import EFFORT_ORDER


def _default_outcome_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


class EffortOutcomeStore:
    """Sync, stdlib-sqlite store of per-effort-decision outcomes. Own table
    (``effort_outcomes``), same DB file as ``route_outcomes`` -- CREATE TABLE
    IF NOT EXISTS is idempotent whichever side creates it first."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else _default_outcome_db()
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
                """CREATE TABLE IF NOT EXISTS effort_outcomes (
                       outcome_id TEXT PRIMARY KEY,
                       ts TEXT NOT NULL,
                       task_class TEXT NOT NULL DEFAULT '',
                       effort TEXT NOT NULL DEFAULT '',
                       quality_signal TEXT NOT NULL DEFAULT 'neutral'
                   )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_effort_outcomes_class "
                "ON effort_outcomes(task_class)"
            )
            conn.commit()
        finally:
            conn.close()

    def record(self, task_class: str, effort: str, quality_signal: object = "neutral",
               ts: str | None = None) -> str:
        signal = normalize_quality_signal(quality_signal)
        ts = ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO effort_outcomes (outcome_id, ts, task_class, effort, quality_signal) "
                "VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, ts, task_class or "", effort or "", signal),
            )
            conn.commit()
        finally:
            conn.close()
        return signal

    def stats(self, task_class: str) -> dict[str, dict[str, int]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT effort, quality_signal, COUNT(*) AS c FROM effort_outcomes "
                "WHERE task_class = ? GROUP BY effort, quality_signal",
                (task_class,),
            ).fetchall()
        finally:
            conn.close()
        out: dict[str, dict[str, int]] = {}
        for r in rows:
            bucket = out.setdefault(r["effort"], {"met": 0, "not_met": 0, "neutral": 0})
            sig = r["quality_signal"] if r["quality_signal"] in bucket else "neutral"
            bucket[sig] += int(r["c"])
        return out


class EffortAdapter:
    """Blend the static effort pick with a learned prior over outcome history.
    Same Beta-posterior / minimum-sample design as ``AdaptiveRouter``, over the
    low -> medium -> high ladder instead of fast -> balanced -> powerful."""

    def __init__(self, store: EffortOutcomeStore | None = None, *, min_samples: int = 5,
                 meet_bar: float = 0.7, fail_bar: float = 0.4,
                 prior_alpha: float = 1.0, prior_beta: float = 1.0,
                 floor: str = "low"):
        self.store = store if store is not None else EffortOutcomeStore()
        self.min_samples = max(1, int(min_samples))
        self.meet_bar = float(meet_bar)
        self.fail_bar = float(fail_bar)
        self.prior_alpha = float(prior_alpha)
        self.prior_beta = float(prior_beta)
        self.floor = floor if floor in EFFORT_ORDER else "low"

    @staticmethod
    def _rank(effort: str) -> int:
        try:
            return EFFORT_ORDER.index(effort)
        except ValueError:
            return EFFORT_ORDER.index("medium")

    def _posterior_mean(self, met: int, total: int) -> float:
        return (met + self.prior_alpha) / (total + self.prior_alpha + self.prior_beta)

    def adapt(self, task_class: str, static_effort: str,
              floor: str | None = None) -> tuple[str, str]:
        floor = floor if (floor in EFFORT_ORDER) else self.floor
        floor_rank = self._rank(floor)
        static_rank = self._rank(static_effort)

        if static_rank < floor_rank:
            static_rank = floor_rank
            static_effort = EFFORT_ORDER[static_rank]

        stats = self.store.stats(task_class)

        # 1) Downgrade: cheapest effort at/above the floor and below the static
        #    pick that has enough evidence of meeting the bar.
        for rank in range(floor_rank, static_rank):
            effort = EFFORT_ORDER[rank]
            d = stats.get(effort)
            if not d:
                continue
            met, not_met = d["met"], d["not_met"]
            total = met + not_met
            if total >= self.min_samples and self._posterior_mean(met, total) >= self.meet_bar:
                reason = (f"{total} past '{task_class}' tasks met the bar at effort "
                          f"'{effort}' (met {met}/{total}); routed to lower effort.")
                return effort, reason

        # 2) Escalate: the static effort itself keeps falling short.
        d = stats.get(static_effort)
        if d and static_rank < len(EFFORT_ORDER) - 1:
            met, not_met = d["met"], d["not_met"]
            total = met + not_met
            if total >= self.min_samples and self._posterior_mean(met, total) <= self.fail_bar:
                up = EFFORT_ORDER[static_rank + 1]
                reason = (f"{total} past '{task_class}' tasks fell short at effort "
                          f"'{static_effort}' (met {met}/{total}); escalated to '{up}'.")
                return up, reason

        # 3) Thin/ambiguous history -> keep the static pick unchanged.
        return static_effort, ""
