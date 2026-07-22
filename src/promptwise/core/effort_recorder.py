"""effort_recorder -- the live-effort outcome writer that closes the learning
loop for the reasoning-effort axis, structurally mirroring route_recorder.py
but over EffortOutcomeStore/EFFORT_ORDER instead of OutcomeStore/TIER_ORDER.

Design contract (same as route_recorder.py):

* **Additive & fail-open.** Any recording error is swallowed and can NEVER
  change or break the effort response -- recording is best-effort telemetry,
  not a gate.
* **No new table / no schema change.** Reuses the existing ``effort_outcomes``
  table (added alongside ``EffortAdapter`` in effort_adapter.py) through the
  sync ``EffortOutcomeStore``.
* **Bounded correlation.** A capped in-process map keyed by a short effort id
  remembers only recent decisions, so a verdict can find its decision without
  any new persistence. Evicted (old) decisions simply stay ``neutral``.
* **Env-gated.** ``PROMPTWISE_EFFORT_RECORDING`` (default ON; ``0/off/false/no``
  disables) turns the whole writer off.
* **Offline, stdlib only.** No network, no new dependency; air-gap safe.
"""
from __future__ import annotations

import os
from collections import OrderedDict

from promptwise.core.effort_adapter import EffortOutcomeStore

# These values disable recording; anything else (incl. unset) leaves it ON.
_RECORDING_OFF = ("0", "off", "false", "no")


def recording_enabled() -> bool:
    """True unless ``PROMPTWISE_EFFORT_RECORDING`` is set to a disabling value."""
    return os.environ.get("PROMPTWISE_EFFORT_RECORDING", "on").strip().lower() not in _RECORDING_OFF


class EffortOutcomeRecorder:
    """Records live effort decisions and correlates later quality verdicts.

    Holds a bounded ``effort_id -> outcome_id`` map so a verdict produced
    elsewhere (a different tool call) can update the decision row it belongs
    to without a new table. ``effort_id`` is returned to the caller in the
    route response.
    """

    def __init__(self, store: EffortOutcomeStore | None = None, db_path: str | None = None,
                 max_pending: int = 512):
        self._store = store
        self._db_path = db_path
        self.max_pending = max(1, int(max_pending))
        self._pending: "OrderedDict[str, str]" = OrderedDict()

    @property
    def store(self) -> EffortOutcomeStore:
        # Lazy so a process that never routes never opens the DB, and so tests
        # can inject a temp-DB store before the first record.
        if self._store is None:
            self._store = EffortOutcomeStore(self._db_path)
        return self._store

    def _remember(self, effort_id: str, outcome_id: str) -> None:
        self._pending[effort_id] = outcome_id
        while len(self._pending) > self.max_pending:
            self._pending.popitem(last=False)  # evict oldest

    def record_decision(self, task_class: str, effort: str) -> str | None:
        """Write a neutral decision row now; return an effort id (or ``None``
        when recording is disabled or anything fails). NEVER raises."""
        if not recording_enabled():
            return None
        try:
            outcome_id = self.store.record_decision(task_class, effort)
            self._remember(outcome_id, outcome_id)  # effort_id == outcome_id
            return outcome_id
        except Exception:
            return None

    def record_verdict(self, effort_id: str | None, signal: object) -> None:
        """Fold a later verdict for ``effort_id`` onto its decision row. No-op
        if recording is disabled, the id is unknown/evicted, or anything
        fails."""
        if not effort_id or not recording_enabled():
            return
        try:
            outcome_id = self._pending.get(effort_id)
            if outcome_id is None:
                return
            self.store.update_signal(outcome_id, signal)
        except Exception:
            return


# ── process-wide recorder (the server's default) ─────────────────────────────
_RECORDER: EffortOutcomeRecorder | None = None


def get_recorder() -> EffortOutcomeRecorder:
    global _RECORDER
    if _RECORDER is None:
        _RECORDER = EffortOutcomeRecorder()
    return _RECORDER


def set_recorder(recorder: EffortOutcomeRecorder | None) -> None:
    """Swap the process recorder (used by tests to point at a temp DB)."""
    global _RECORDER
    _RECORDER = recorder


def record_effort_decision(task_class: str, effort: str) -> str | None:
    """Module entry point: record a live effort decision. Fail-open, returns
    an effort id or ``None``."""
    return get_recorder().record_decision(task_class, effort)


def record_effort_verdict(effort_id: str | None, signal: object) -> None:
    """Module entry point: correlate a later quality verdict onto a prior
    effort decision.

    Call this from wherever a verdict for a known ``effort_id`` is produced
    (e.g. ``validate_output`` / ``run_quality_gate`` when passed an
    ``effort_id``). Fail-open; never raises.
    """
    get_recorder().record_verdict(effort_id, signal)
