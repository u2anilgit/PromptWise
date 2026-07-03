"""route_recorder — the live-route outcome writer that closes the learning loop.

Phase 8 WP8.1. Static/adaptive routing decides a tier; 7.1's ``OutcomeStore`` can
*learn* from outcomes — but nothing was feeding real live routes into it. This
module is that seam: every ``route_request`` records ONE ``route_outcomes``
decision row (``neutral`` signal, written immediately), and when a later quality
verdict for that same decision surfaces (quality-gate verdict / ``validate_output``
/ a captured correction) the signal is resolved via ``normalize_quality_signal``
and folded back onto the row.

Design contract:

* **Additive & fail-open.** Any recording error is swallowed and can NEVER change
  or break the route response — recording is best-effort telemetry, not a gate.
* **No new table / no schema change.** Reuses the existing ``route_outcomes``
  table through the sync ``OutcomeStore`` (the preferred hot-path store).
* **Bounded correlation.** A capped in-process map keyed by a short route id
  remembers only recent decisions, so a verdict can find its decision without any
  new persistence. Evicted (old) decisions simply stay ``neutral``.
* **Env-gated.** ``PROMPTWISE_ROUTE_RECORDING`` (default ON; ``0/off/false/no``
  disables) turns the whole writer off.
* **Offline, stdlib only.** No network, no new dependency; air-gap safe.
"""
from __future__ import annotations

import os
from collections import OrderedDict

from promptwise.core.adaptive_router import OutcomeStore

# These values disable recording; anything else (incl. unset) leaves it ON.
_RECORDING_OFF = ("0", "off", "false", "no")


def recording_enabled() -> bool:
    """True unless ``PROMPTWISE_ROUTE_RECORDING`` is set to a disabling value."""
    return os.environ.get("PROMPTWISE_ROUTE_RECORDING", "on").strip().lower() not in _RECORDING_OFF


class RouteOutcomeRecorder:
    """Records live route decisions and correlates later quality verdicts.

    Holds a bounded ``route_id -> outcome_id`` map so a verdict produced elsewhere
    (a different tool call) can update the decision row it belongs to without a new
    table. ``route_id`` is returned to the caller in the route response.
    """

    def __init__(self, store: OutcomeStore | None = None, db_path: str | None = None,
                 max_pending: int = 512):
        self._store = store
        self._db_path = db_path
        self.max_pending = max(1, int(max_pending))
        self._pending: "OrderedDict[str, str]" = OrderedDict()

    @property
    def store(self) -> OutcomeStore:
        # Lazy so a process that never routes never opens the DB, and so tests can
        # inject a temp-DB store before the first record.
        if self._store is None:
            self._store = OutcomeStore(self._db_path)
        return self._store

    def _remember(self, route_id: str, outcome_id: str) -> None:
        self._pending[route_id] = outcome_id
        while len(self._pending) > self.max_pending:
            self._pending.popitem(last=False)  # evict oldest

    def record_decision(self, task_class: str, tier: str, model_family: str = "",
                        cost: float = 0.0) -> str | None:
        """Write a neutral decision row now; return a route id (or ``None`` when
        recording is disabled or anything fails). NEVER raises."""
        if not recording_enabled():
            return None
        try:
            outcome_id = self.store.record_decision(
                task_class, tier, model_family=model_family, cost=cost)
            self._remember(outcome_id, outcome_id)  # route_id == outcome_id
            return outcome_id
        except Exception:
            return None

    def record_verdict(self, route_id: str | None, signal: object) -> None:
        """Fold a later verdict for ``route_id`` onto its decision row. No-op if
        recording is disabled, the id is unknown/evicted, or anything fails."""
        if not route_id or not recording_enabled():
            return
        try:
            outcome_id = self._pending.get(route_id)
            if outcome_id is None:
                return
            self.store.update_signal(outcome_id, signal)
        except Exception:
            return


# ── process-wide recorder (the server's default) ─────────────────────────────
_RECORDER: RouteOutcomeRecorder | None = None


def get_recorder() -> RouteOutcomeRecorder:
    global _RECORDER
    if _RECORDER is None:
        _RECORDER = RouteOutcomeRecorder()
    return _RECORDER


def set_recorder(recorder: RouteOutcomeRecorder | None) -> None:
    """Swap the process recorder (used by tests to point at a temp DB)."""
    global _RECORDER
    _RECORDER = recorder


def record_route_decision(task_class: str, tier: str, model_family: str = "",
                          cost: float = 0.0) -> str | None:
    """Module entry point: record a live route decision. Fail-open, returns a
    route id or ``None``."""
    return get_recorder().record_decision(task_class, tier, model_family=model_family, cost=cost)


def record_route_verdict(route_id: str | None, signal: object) -> None:
    """Module entry point: correlate a later quality verdict onto a prior route.

    Call this from wherever a verdict for a known ``route_id`` is produced
    (e.g. ``validate_output`` / ``run_quality_gate`` when passed a ``route_id``).
    Fail-open; never raises.
    """
    get_recorder().record_verdict(route_id, signal)
