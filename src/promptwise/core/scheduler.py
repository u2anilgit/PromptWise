"""core/scheduler - pull-based due-check that drives periodic report export
(core/report_export.py). No background daemon by default: run_if_due()
compares a small local marker file against a configured interval
(config/reports.yaml) and generates a report only when due. This is invoked
the same way other periodic PromptWise behavior already runs - from a hook
(SessionStart), or manually via `promptwise report-scheduler --once` - never
a persistent process started implicitly.

run_forever() is an explicit opt-in daemon mode (stdlib time.sleep loop, no
new dependency) for anyone who wants a real background cadence instead of the
hook-driven pull model; nothing in PromptWise starts it automatically.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:  # PyYAML is already a PromptWise dependency
    import yaml
except Exception:  # pragma: no cover - yaml always present in practice
    yaml = None  # type: ignore

_DEFAULT_CONFIG_PATH = Path("config") / "reports.yaml"
_MARKER_FILE = "last_report.json"
_EXT = {"markdown": "md", "html": "html"}


@dataclass
class ScheduleConfig:
    enabled: bool = False
    interval_hours: float = 24.0
    format: str = "markdown"
    output_dir: str = ".promptwise/reports"


def load_schedule_config(path: str | Path | None = None) -> ScheduleConfig:
    p = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not p.exists():
        return ScheduleConfig()
    try:
        text = p.read_text(encoding="utf-8")
        raw = yaml.safe_load(text) if yaml is not None else json.loads(text)
        if not isinstance(raw, dict):
            return ScheduleConfig()
    except Exception:
        return ScheduleConfig()
    return ScheduleConfig(
        enabled=bool(raw.get("enabled", False)),
        interval_hours=float(raw.get("interval_hours", 24.0)),
        format=str(raw.get("format", "markdown")),
        output_dir=str(raw.get("output_dir", ".promptwise/reports")),
    )


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_due(last_run_iso: str | None, now_iso: str, interval_hours: float) -> bool:
    """True if a report has never run, or the configured interval has
    elapsed since the last run. Fails soft toward "due" on a bad timestamp -
    a corrupt marker should never silently stop reporting forever."""
    if not last_run_iso:
        return True
    try:
        last = _parse_iso(last_run_iso)
        now = _parse_iso(now_iso)
    except Exception:
        return True
    return (now - last).total_seconds() >= interval_hours * 3600


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_if_due(*, state_dir: str | Path, repo_root: str | Path = ".",
               config: ScheduleConfig | None = None, now_iso: str | None = None,
               window_days: int = 30) -> dict:
    """The hook-friendly entry point: no-op unless enabled and due, then
    generates + writes a report via core/report_export.py and advances the
    marker. Never raises - any generation error is reported, not propagated."""
    config = config or load_schedule_config()
    if not config.enabled:
        return {"ran": False, "reason": "disabled"}

    state_dir = Path(state_dir)
    marker_path = state_dir / _MARKER_FILE
    last_run = None
    if marker_path.exists():
        try:
            last_run = json.loads(marker_path.read_text(encoding="utf-8")).get("last_run")
        except Exception:
            last_run = None

    now_iso = now_iso or _now_iso()
    if not is_due(last_run, now_iso, config.interval_hours):
        return {"ran": False, "reason": "not_due"}

    try:
        from promptwise.core import report_export as rex
        ext = _EXT.get(config.format, "md")
        stamp = now_iso.replace(":", "").replace("-", "")
        out_path = Path(repo_root) / config.output_dir / f"report_{stamp}.{ext}"
        result = rex.export_report(repo_root=repo_root, window_days=window_days,
                                   out_path=out_path, fmt=config.format)
        if not result.get("written"):
            return {"ran": False, "reason": "generation_failed", "error": result.get("error", "unknown")}
        state_dir.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps({"last_run": now_iso, "path": result.get("path")}), encoding="utf-8")
        return {"ran": True, "reason": "generated", "path": result.get("path")}
    except Exception as e:  # fail-soft: the scheduler must never wedge a hook
        return {"ran": False, "reason": "error", "error": f"{type(e).__name__}: {e}"}


def run_forever(*, interval_seconds: float = 3600.0, state_dir: str | Path = ".promptwise",
                repo_root: str | Path = ".", config: ScheduleConfig | None = None,
                max_iterations: int | None = None) -> None:
    """Opt-in stdlib daemon mode: sleeps interval_seconds between due-checks.
    Never started by PromptWise itself - only by an explicit
    `promptwise report-scheduler --daemon` invocation. max_iterations bounds
    the loop for tests; omit it (None) to run until the process is killed."""
    n = 0
    while max_iterations is None or n < max_iterations:
        run_if_due(state_dir=state_dir, repo_root=repo_root, config=config)
        n += 1
        if max_iterations is None or n < max_iterations:
            time.sleep(interval_seconds)
