"""playbooks -- YAML-driven incident response playbooks. Reuses
core/governor.py's exact autonomy-gating pattern: a PROMPTWISE_AUTONOMY
env var (advise default / dry_run / apply), a per-call `mode` argument
that overrides the env var, and a conservative fallback to "advise" on
any unrecognized mode value -- NOT a new autonomy mechanism. A step only
actually executes when the resolved mode is "apply"; advise/dry_run
record a "would_apply" result and change nothing, matching
Governor._resolve_mode / Governor's advise-vs-apply branch (governor.py).
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:  # PyYAML is already a PromptWise dependency (see core/governor.py's own import style)
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

_ENV_MODE = "PROMPTWISE_AUTONOMY"
_MODE_ADVISE = "advise"
_MODE_DRY_RUN = "dry_run"
_MODE_APPLY = "apply"
_VALID_MODES = {_MODE_ADVISE, _MODE_DRY_RUN, _MODE_APPLY}


def _resolve_mode(mode: str | None) -> str:
    m = mode if mode is not None else os.environ.get(_ENV_MODE, _MODE_ADVISE)
    m = str(m).strip().lower()
    return m if m in _VALID_MODES else _MODE_ADVISE  # unknown -> conservative


@dataclass
class PlaybookStep:
    name: str
    action: str
    params: dict = field(default_factory=dict)
    on_failure: str = "halt"  # "halt" | "continue"


@dataclass
class Playbook:
    name: str
    description: str
    steps: list[PlaybookStep] = field(default_factory=list)


@dataclass
class StepResult:
    step_name: str
    status: str  # "would_apply" | "applied" | "failed"
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlaybookRun:
    playbook_name: str
    mode: str
    results: list[StepResult] = field(default_factory=list)
    halted_at: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d


def load_playbook(path: str | Path) -> Playbook:
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML not available")
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    steps = [
        PlaybookStep(
            name=s.get("name", ""), action=s.get("action", ""),
            params=s.get("params", {}) or {}, on_failure=s.get("on_failure", "halt"))
        for s in data.get("steps", []) or []
    ]
    return Playbook(name=data.get("name", ""), description=data.get("description", ""), steps=steps)


def run_playbook(playbook: Playbook, *, mode: str | None = None, executor=None) -> PlaybookRun:
    """Execute (or dry-run) a playbook's steps in order.

    `executor(step: PlaybookStep) -> bool` is called once per step ONLY
    when the resolved mode is "apply" -- advise/dry_run never call it,
    matching Governor's advise/dry_run branch which "would apply, but
    change nothing". Defaults to a no-op stub for callers that only care
    about advise/dry_run behavior."""
    resolved = _resolve_mode(mode)
    executor = executor or (lambda step: True)
    run = PlaybookRun(playbook_name=playbook.name, mode=resolved)

    for step in playbook.steps:
        if resolved != _MODE_APPLY:
            run.results.append(StepResult(step_name=step.name, status="would_apply"))
            continue
        ok = executor(step)
        if ok:
            run.results.append(StepResult(step_name=step.name, status="applied"))
        else:
            run.results.append(StepResult(step_name=step.name, status="failed"))
            if step.on_failure != "continue":
                run.halted_at = step.name
                break
    return run
