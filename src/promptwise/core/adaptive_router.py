"""adaptive_router — routing that learns from its own outcome history.

Static routing (tier by intent/stakes) never gets smarter from what it produced.
This module closes that loop: every route decision can be recorded with a
normalized quality signal, and a bounded, stable estimator blends that history
into the next decision — preferring the *cheapest* tier that has historically
met the quality bar for a task class, and escalating a class that keeps failing
at a cheap tier.

Design contract (matches ``router.py`` / ``model_registry.py`` conventions):

* **Tiers, never branded ids.** Everything here reasons over the abstract tier
  ladder ``fast -> balanced -> powerful``. Concrete model resolution (and the
  never-select-a-deprecated-model rule) stays in the registry/router.
* **Additive & fail-open.** Absence of history reproduces the static pick
  exactly; the caller wraps ``adapt`` so any error falls back to static.
* **Bounded & stable.** A Beta-style posterior with a minimum-sample threshold
  keeps a couple of lucky (or unlucky) runs from swinging the route.
* **Absence is neutral, never negative.** A missing/soft signal counts toward
  nothing — it can never by itself demote a tier.
* **Offline, stdlib only.** Python's bundled ``sqlite3`` into the local
  PromptWise DB; no server, no network, air-gap safe.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

# Cheapest -> most expensive. The one place the ladder order is defined.
TIER_ORDER: tuple[str, ...] = ("fast", "balanced", "powerful")

# Signal vocabularies. Normalization folds the existing PromptWise signals
# (quality-gate verdict, validate_output, captured corrections) onto met/not-met.
_MET = {"met", "pass", "passed", "waived", "ok", "valid", "good", "true",
        "success", "succeeded"}
_NOT_MET = {"not_met", "fail", "failed", "invalid", "bad", "false", "error",
            "correction", "regression"}


def normalize_quality_signal(raw: object) -> str:
    """Fold an existing signal onto ``"met"`` / ``"not_met"`` / ``"neutral"``.

    Fail-open: anything unrecognised (or absent) is ``"neutral"`` — it never
    counts as a failure, so a missing signal can never demote a tier.
    """
    if raw is None:
        return "neutral"
    if isinstance(raw, bool):
        return "met" if raw else "not_met"
    if isinstance(raw, dict):
        # validate_output-style dicts, then quality-gate-style dicts.
        for key in ("valid", "ok", "passed", "success"):
            if key in raw:
                return "met" if raw[key] else "not_met"
        if "decision" in raw:
            raw = raw["decision"]
        else:
            return "neutral"
    s = str(raw).strip().lower()
    if s in ("met", "not_met", "neutral"):
        return s
    if s in _MET:
        return "met"
    if s in _NOT_MET:
        return "not_met"
    # Quality-gate CONCERNS is a soft signal: neutral, never negative.
    return "neutral"


def _default_outcome_db() -> Path:
    """Share the local PromptWise DB so the async ``db/models`` accessors and
    this sync hot-path read/write the same ``route_outcomes`` table."""
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


class OutcomeStore:
    """Sync, stdlib-sqlite store of per-route-decision outcomes.

    Schema mirrors ``db.models.RouteOutcomeModel`` (same table + columns) so the
    two paths interoperate on one file. ``CREATE TABLE IF NOT EXISTS`` is
    idempotent whichever side creates it first.
    """

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
                """CREATE TABLE IF NOT EXISTS route_outcomes (
                       outcome_id TEXT PRIMARY KEY,
                       ts TEXT NOT NULL,
                       task_class TEXT NOT NULL DEFAULT '',
                       tier TEXT NOT NULL DEFAULT '',
                       model_family TEXT NOT NULL DEFAULT '',
                       cost REAL NOT NULL DEFAULT 0,
                       quality_signal TEXT NOT NULL DEFAULT 'neutral'
                   )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_route_outcomes_class "
                "ON route_outcomes(task_class)"
            )
            conn.commit()
        finally:
            conn.close()

    def record(self, task_class: str, tier: str, quality_signal: object = "neutral",
               model_family: str = "", cost: float = 0.0, ts: str | None = None) -> str:
        """Persist one decision outcome; returns the normalized signal stored."""
        signal = normalize_quality_signal(quality_signal)
        ts = ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO route_outcomes "
                "(outcome_id, ts, task_class, tier, model_family, cost, quality_signal) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, ts, task_class or "", tier or "",
                 model_family or "", float(cost or 0.0), signal),
            )
            conn.commit()
        finally:
            conn.close()
        return signal

    def stats(self, task_class: str) -> dict[str, dict[str, int]]:
        """Per-tier counts for a class: ``{tier: {met, not_met, neutral}}``."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT tier, quality_signal, COUNT(*) AS c FROM route_outcomes "
                "WHERE task_class = ? GROUP BY tier, quality_signal",
                (task_class,),
            ).fetchall()
        finally:
            conn.close()
        out: dict[str, dict[str, int]] = {}
        for r in rows:
            bucket = out.setdefault(r["tier"], {"met": 0, "not_met": 0, "neutral": 0})
            sig = r["quality_signal"] if r["quality_signal"] in bucket else "neutral"
            bucket[sig] += int(r["c"])
        return out


class AdaptiveRouter:
    """Blend the static tier pick with a learned prior over outcome history.

    ``adapt(task_class, static_tier)`` returns ``(tier, reason)``. With thin
    history it returns the static tier and an empty reason (caller keeps its own
    reason string). It never returns a tier below ``floor``.
    """

    def __init__(self, store: OutcomeStore | None = None, *, min_samples: int = 5,
                 meet_bar: float = 0.7, fail_bar: float = 0.4,
                 prior_alpha: float = 1.0, prior_beta: float = 1.0,
                 floor: str = "fast"):
        self.store = store if store is not None else OutcomeStore()
        self.min_samples = max(1, int(min_samples))
        self.meet_bar = float(meet_bar)
        self.fail_bar = float(fail_bar)
        self.prior_alpha = float(prior_alpha)
        self.prior_beta = float(prior_beta)
        self.floor = floor if floor in TIER_ORDER else "fast"

    @staticmethod
    def _rank(tier: str) -> int:
        try:
            return TIER_ORDER.index(tier)
        except ValueError:
            return TIER_ORDER.index("balanced")  # unknown -> middle, stays safe

    def _posterior_mean(self, met: int, total: int) -> float:
        """Beta-style posterior mean of the met-rate — bounded and stable so a
        couple of samples can never swing the estimate to 0 or 1."""
        return (met + self.prior_alpha) / (total + self.prior_alpha + self.prior_beta)

    def adapt(self, task_class: str, static_tier: str,
              floor: str | None = None) -> tuple[str, str]:
        floor = floor if (floor in TIER_ORDER) else self.floor
        floor_rank = self._rank(floor)
        static_rank = self._rank(static_tier)

        # A static pick below the floor is raised to the floor first.
        if static_rank < floor_rank:
            static_rank = floor_rank
            static_tier = TIER_ORDER[static_rank]

        stats = self.store.stats(task_class)

        # 1) Downgrade: cheapest tier at/above the floor and below the static
        #    pick that has enough evidence of meeting the bar.
        for rank in range(floor_rank, static_rank):
            tier = TIER_ORDER[rank]
            d = stats.get(tier)
            if not d:
                continue
            met, not_met = d["met"], d["not_met"]
            total = met + not_met
            if total >= self.min_samples and self._posterior_mean(met, total) >= self.meet_bar:
                reason = (f"{total} past '{task_class}' tasks met the bar at tier "
                          f"'{tier}' (met {met}/{total}); routed to the cheaper tier.")
                return tier, reason

        # 2) Escalate: the static tier itself keeps falling short.
        d = stats.get(static_tier)
        if d and static_rank < len(TIER_ORDER) - 1:
            met, not_met = d["met"], d["not_met"]
            total = met + not_met
            if total >= self.min_samples and self._posterior_mean(met, total) <= self.fail_bar:
                up = TIER_ORDER[static_rank + 1]
                reason = (f"{total} past '{task_class}' tasks fell short at tier "
                          f"'{static_tier}' (met {met}/{total}); escalated to '{up}'.")
                return up, reason

        # 3) Thin/ambiguous history -> keep the static pick unchanged.
        return static_tier, ""
