"""doctor — self-check that the PromptWise plugin is healthy, and a one-shot
bootstrap that creates the local state it needs. Stdlib only, no network.

`run_diagnostics()` verifies the things that silently break a plugin install:
hooks are registered, the state dir is writable, core engines import, policy and
the model registry are present. `bootstrap()` creates the project-local
`.promptwise/` state and the learning DB so a first run has somewhere to write.
Both are safe to run repeatedly and never raise.
"""
from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Core engines whose import failure would break enforcement/routing silently.
_CORE_MODULES = [
    "promptwise.core.hook_bridge",
    "promptwise.core.router",
    "promptwise.core.model_registry",
    "promptwise.core.responsible_ai",
    "promptwise.security.scanner",
    "promptwise.core.quality_gate",
    "promptwise.core.audit_log",
    "promptwise.core.learning_store",
]


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail}


def _state_dir(cwd: str | Path | None = None) -> Path:
    base = Path(cwd) if cwd else Path.cwd()
    return base / ".promptwise"


def run_diagnostics(cwd: str | Path | None = None) -> dict:
    """Return a health report: a list of checks plus an overall ok flag."""
    checks: list[dict] = []

    # 1) hooks registered
    try:
        hooks_json = _REPO_ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_json.read_text(encoding="utf-8")) if hooks_json.exists() else {}
        events = list((data.get("hooks") or {}).keys())
        checks.append(_check("hooks registered", bool(events),
                             f"{len(events)} event(s): {', '.join(events)}" if events else "hooks.json missing/empty"))
    except Exception as e:
        checks.append(_check("hooks registered", False, f"{type(e).__name__}: {e}"))

    # 2) state dir writable
    try:
        d = _state_dir(cwd)
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".doctor_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks.append(_check("state dir writable", True, str(d)))
    except Exception as e:
        checks.append(_check("state dir writable", False, f"{type(e).__name__}: {e}"))

    # 3) core modules import
    failed = []
    for mod in _CORE_MODULES:
        try:
            __import__(mod)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{mod} ({type(e).__name__})")
    checks.append(_check("core modules import", not failed,
                         "all import" if not failed else "failed: " + "; ".join(failed)))

    # 4) policy present
    policy = _REPO_ROOT / "config" / "policy.yaml"
    checks.append(_check("policy present", policy.exists(), str(policy)))

    # 5) model registry loads
    try:
        from promptwise.core.model_registry import ModelRegistry
        reg = ModelRegistry()
        n = len(reg.all_aliases())
        checks.append(_check("model registry loads", reg.loaded,
                             f"{n} model(s), current: {', '.join(reg.all_current())}" if reg.loaded
                             else "config/models.yaml missing — routing uses config fallbacks"))
    except Exception as e:
        checks.append(_check("model registry loads", False, f"{type(e).__name__}: {e}"))

    # 6) learning store writable
    try:
        from promptwise.core.learning_store import LearningStore
        LearningStore()  # opens/creates ~/.promptwise/learning.db
        checks.append(_check("learning store writable", True, "learning.db opened"))
    except Exception as e:
        checks.append(_check("learning store writable", False, f"{type(e).__name__}: {e}"))

    overall = all(c["ok"] for c in checks)
    return {"ok": overall, "checks": checks,
            "summary": f"{sum(c['ok'] for c in checks)}/{len(checks)} checks passed"}


def bootstrap(cwd: str | Path | None = None) -> dict:
    """Create the project-local state a first run needs. Idempotent, fail-soft."""
    created: list[str] = []
    try:
        d = _state_dir(cwd)
        existed = d.exists()
        d.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(str(d))
        try:
            from promptwise.core.learning_store import LearningStore
            LearningStore()  # initialises the schema if absent
        except Exception:
            pass
        return {"ok": True, "state_dir": str(d), "created": created}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "created": created}


def format_report(report: dict) -> str:
    """Human-readable one-line-per-check rendering for the CLI / doctor command."""
    lines = [f"PromptWise doctor — {report.get('summary', '')}"]
    for c in report.get("checks", []):
        mark = "OK " if c["ok"] else "FAIL"
        lines.append(f"  [{mark}] {c['check']}: {c['detail']}")
    lines.append("overall: " + ("healthy" if report.get("ok") else "issues found"))
    return "\n".join(lines)
