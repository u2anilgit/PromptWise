"""technique_recorder -- the live-technique outcome writer that closes the
learning loop for the prompting-technique axis, structurally mirroring
effort_recorder.py but over TechniqueOutcomeStore instead of
EffortOutcomeStore.

Design contract (same as route_recorder.py / effort_recorder.py):

* Additive & fail-open. Any recording error is swallowed and can NEVER
  change or break suggest_technique's own response.
* No new table beyond technique_outcomes (added alongside TechniqueAdapter).
* Bounded correlation via an in-process technique_id -> outcome_id map.
* Env-gated: PROMPTWISE_TECHNIQUE_RECORDING (default ON) turns it off.
* Offline, stdlib only.
"""
from __future__ import annotations

import os
from collections import OrderedDict

from promptwise.core.technique_adapter import TechniqueOutcomeStore

_RECORDING_OFF = ("0", "off", "false", "no")


def recording_enabled() -> bool:
    return os.environ.get("PROMPTWISE_TECHNIQUE_RECORDING", "on").strip().lower() not in _RECORDING_OFF


class TechniqueOutcomeRecorder:
    def __init__(self, store: TechniqueOutcomeStore | None = None, db_path: str | None = None,
                 max_pending: int = 512):
        self._store = store
        self._db_path = db_path
        self.max_pending = max(1, int(max_pending))
        self._pending: "OrderedDict[str, str]" = OrderedDict()

    @property
    def store(self) -> TechniqueOutcomeStore:
        if self._store is None:
            self._store = TechniqueOutcomeStore(self._db_path)
        return self._store

    def _remember(self, technique_id: str, outcome_id: str) -> None:
        self._pending[technique_id] = outcome_id
        while len(self._pending) > self.max_pending:
            self._pending.popitem(last=False)

    def record_decision(self, task_class: str, technique: str) -> str | None:
        if not recording_enabled():
            return None
        try:
            outcome_id = self.store.record_decision(task_class, technique)
            self._remember(outcome_id, outcome_id)
            return outcome_id
        except Exception:
            return None

    def record_verdict(self, technique_id: str | None, signal: object) -> None:
        if not technique_id or not recording_enabled():
            return
        try:
            outcome_id = self._pending.get(technique_id)
            if outcome_id is None:
                return
            self.store.update_signal(outcome_id, signal)
        except Exception:
            return


_RECORDER: TechniqueOutcomeRecorder | None = None


def get_recorder() -> TechniqueOutcomeRecorder:
    global _RECORDER
    if _RECORDER is None:
        _RECORDER = TechniqueOutcomeRecorder()
    return _RECORDER


def set_recorder(recorder: TechniqueOutcomeRecorder | None) -> None:
    global _RECORDER
    _RECORDER = recorder


def record_technique_decision(task_class: str, technique: str) -> str | None:
    return get_recorder().record_decision(task_class, technique)


def record_technique_verdict(technique_id: str | None, signal: object) -> None:
    get_recorder().record_verdict(technique_id, signal)
