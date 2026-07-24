"""technique_adapter -- prompting-technique selection that learns from its
own outcome history. Structurally mirrors effort_adapter.py's
EffortOutcomeStore/EffortAdapter split, but over a CATEGORICAL choice
(CRAFT/Few-Shot/Chain-of-Thought/Chaining/...) instead of an ordered ladder --
technique is not "cheaper" or "more expensive," so adapt() asks "has another
technique clearly outperformed the static pick for this task class," not
"can we downgrade/escalate."

Design contract (same as adaptive_router.py / effort_adapter.py):

* Additive & fail-open. Absence of history reproduces the static pick exactly.
* Bounded & stable. Beta-style posterior mean + minimum-sample threshold.
* Absence is neutral, never negative.
* Offline, stdlib only.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from promptwise.core.adaptive_router import normalize_quality_signal


def _default_outcome_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


class TechniqueOutcomeStore:
    """Sync, stdlib-sqlite store of per-technique-decision outcomes. Own table
    (``technique_outcomes``), same DB file as ``route_outcomes``/
    ``effort_outcomes`` -- CREATE TABLE IF NOT EXISTS is idempotent."""

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
                """CREATE TABLE IF NOT EXISTS technique_outcomes (
                       outcome_id TEXT PRIMARY KEY,
                       ts TEXT NOT NULL,
                       task_class TEXT NOT NULL DEFAULT '',
                       technique TEXT NOT NULL DEFAULT '',
                       quality_signal TEXT NOT NULL DEFAULT 'neutral'
                   )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_technique_outcomes_class "
                "ON technique_outcomes(task_class)"
            )
            conn.commit()
        finally:
            conn.close()

    def record(self, task_class: str, technique: str, quality_signal: object = "neutral",
               ts: str | None = None) -> str:
        signal = normalize_quality_signal(quality_signal)
        ts = ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO technique_outcomes (outcome_id, ts, task_class, technique, quality_signal) "
                "VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, ts, task_class or "", technique or "", signal),
            )
            conn.commit()
        finally:
            conn.close()
        return signal

    def record_decision(self, task_class: str, technique: str, ts: str | None = None) -> str:
        """Insert a fresh decision row with a ``neutral`` signal; returns its
        ``outcome_id`` for later verdict correlation via :meth:`update_signal`."""
        outcome_id = uuid.uuid4().hex
        ts = ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO technique_outcomes (outcome_id, ts, task_class, technique, quality_signal) "
                "VALUES (?, ?, ?, ?, ?)",
                (outcome_id, ts, task_class or "", technique or "", "neutral"),
            )
            conn.commit()
        finally:
            conn.close()
        return outcome_id

    def update_signal(self, outcome_id: str, quality_signal: object) -> str:
        signal = normalize_quality_signal(quality_signal)
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE technique_outcomes SET quality_signal = ? WHERE outcome_id = ?",
                (signal, outcome_id),
            )
            conn.commit()
        finally:
            conn.close()
        return signal

    def stats(self, task_class: str) -> dict[str, dict[str, int]]:
        """Per-technique counts for a class: ``{technique: {met, not_met, neutral}}``."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT technique, quality_signal, COUNT(*) AS c FROM technique_outcomes "
                "WHERE task_class = ? GROUP BY technique, quality_signal",
                (task_class,),
            ).fetchall()
        finally:
            conn.close()
        out: dict[str, dict[str, int]] = {}
        for r in rows:
            bucket = out.setdefault(r["technique"], {"met": 0, "not_met": 0, "neutral": 0})
            sig = r["quality_signal"] if r["quality_signal"] in bucket else "neutral"
            bucket[sig] += int(r["c"])
        return out


class TechniqueAdapter:
    """Blend the static heuristic technique pick with learned outcome history.

    Unlike AdaptiveRouter/EffortAdapter (ordered ladders), technique is
    categorical: adapt() looks for another technique with strong evidence of
    outperforming the static pick for this task class, rather than moving up
    or down a fixed order.
    """

    def __init__(self, store: TechniqueOutcomeStore | None = None, *, min_samples: int = 5,
                 meet_bar: float = 0.7, margin: float = 0.1,
                 prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self.store = store if store is not None else TechniqueOutcomeStore()
        self.min_samples = max(1, int(min_samples))
        self.meet_bar = float(meet_bar)
        self.margin = float(margin)
        self.prior_alpha = float(prior_alpha)
        self.prior_beta = float(prior_beta)

    def _posterior_mean(self, met: int, total: int) -> float:
        return (met + self.prior_alpha) / (total + self.prior_alpha + self.prior_beta)

    def adapt(self, task_class: str, static_technique: str) -> tuple[str, str]:
        stats = self.store.stats(task_class)

        qualifying: list[tuple[str, float, int]] = []
        for technique, d in stats.items():
            met, not_met = d["met"], d["not_met"]
            total = met + not_met
            if total >= self.min_samples:
                qualifying.append((technique, self._posterior_mean(met, total), total))

        if not qualifying:
            return static_technique, ""

        static_entry = next((q for q in qualifying if q[0] == static_technique), None)
        static_mean = static_entry[1] if static_entry else None

        best = max(qualifying, key=lambda q: q[1])
        best_technique, best_mean, best_total = best

        if best_technique == static_technique:
            return static_technique, ""

        if best_mean < self.meet_bar:
            return static_technique, ""

        if static_mean is not None and best_mean < static_mean + self.margin:
            return static_technique, ""

        reason = (f"{best_total} past '{task_class}' tasks met the bar with technique "
                  f"'{best_technique}' (met rate {best_mean:.2f}); switched from '{static_technique}'.")
        return best_technique, reason
