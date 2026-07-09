"""core/statusline - an at-a-glance terminal badge, e.g.
"budget: 40% used | last scan: 2h ago". Reuses the exact state the dashboard
already reads: plugins/budget.py's effective_limit() (the same overlay
resolution BudgetGuardian uses) plus a sync sum over the shared cost_logs DB,
and core/security_log.SecurityScanStore for the last recorded scan. No new
state store.

Pure sync stdlib I/O (sqlite3 directly, not the async SQLAlchemy layer) so
this runs instantly from a shell prompt / Claude Code statusline hook.
Exposed two ways so it works whether or not the package is pip-installed:
`promptwise statusline` (see cli.py) and `python -m promptwise.core.statusline`
directly - the thin hooks/promptwise-statusline.sh / .ps1 wrappers use the
latter.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def gather_status() -> dict:
    """Current budget usage (pct/used/limit) + the last security-scan
    timestamp. Fails soft per source - a missing/unreadable DB degrades to
    zeroed/unknown values, never raises."""
    limit = 10.0
    used = 0.0
    try:
        from promptwise.plugins.budget import effective_limit
        limit = effective_limit(None)
    except Exception:
        pass
    try:
        from promptwise.db.models import get_db_path
        db_path = Path(get_db_path())
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            try:
                row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM cost_logs").fetchone()
                used = float(row[0] or 0.0)
            finally:
                conn.close()
    except Exception:
        used = 0.0

    last_scan_iso = None
    try:
        from promptwise.core.security_log import SecurityScanStore
        results = SecurityScanStore().results(limit=1)
        if results:
            last_scan_iso = results[0].get("ts")
    except Exception:
        last_scan_iso = None

    pct = round(used / limit * 100, 1) if limit else 0.0
    return {
        "budget_used_usd": round(used, 4),
        "budget_limit_usd": limit,
        "budget_pct": pct,
        "last_scan_iso": last_scan_iso,
    }


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _time_ago(iso_ts: str | None, now_iso: str | None = None) -> str:
    if not iso_ts:
        return "never"
    try:
        then = _parse_iso(iso_ts)
        now = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)
        delta = (now - then).total_seconds()
    except Exception:
        return "unknown"
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def format_statusline(status: dict, now_iso: str | None = None) -> str:
    """Pure formatting: {"budget: N% used | last scan: <time-ago>"}."""
    pct = int(round(float(status.get("budget_pct", 0) or 0)))
    ago = _time_ago(status.get("last_scan_iso"), now_iso)
    return f"budget: {pct}% used | last scan: {ago}"


def render_status() -> str:
    """gather_status() + format_statusline() in one call - what the CLI
    subcommand and the hook scripts actually invoke. Never raises: any
    failure degrades to a placeholder line rather than a crash (a statusline
    that errors is worse than one that's briefly wrong)."""
    try:
        return format_statusline(gather_status())
    except Exception:
        return "budget: -- | last scan: --"


if __name__ == "__main__":
    print(render_status())
