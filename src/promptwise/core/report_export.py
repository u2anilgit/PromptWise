"""core/report_export - a periodic summary (spend, security-scan verdicts,
governance/governor actions) for a stakeholder who does not touch a CLI -
"are we governing AI responsibly" answered without a terminal.

Mirrors core/compliance_export.py's shape: a pure build_report() over
already-gathered inputs, then a renderer. No PDF dependency - Markdown or a
self-contained HTML file, the same "stdlib templating" approach
dashboard/web.py already uses for its own page. Every gather_* function is
sync stdlib I/O (sqlite3 directly against the shared local DB, the same one
core/security_log.py and dashboard/retention.py already read) so this module
never needs the async SQLAlchemy layer and can run from a hook.

gather_report_data() assembles the three sections fail-soft per source - the
convention core/context_ranker.py (Phase 12) established: a broken source
drops its section, never fails the whole call.
"""
from __future__ import annotations

import html as _html
import json
import sqlite3
import time
from pathlib import Path

_TITLE = "PromptWise — Governance & Spend Report"


# -- gather: spend (sync sqlite3 against the shared local DB) ----------------
def gather_spend_summary(db_path: str | Path | None = None, window_days: int = 30) -> dict:
    """Sum cost_logs the same way dashboard/retention.py rolls them up, but via
    sync sqlite3 (not the async SQLAlchemy engine) so this can run from a hook.
    Missing DB / table -> zeroed summary, never raises."""
    try:
        if db_path is None:
            from promptwise.db.models import get_db_path
            db_path = get_db_path()
        db_path = Path(db_path)
        if not db_path.exists():
            return {"total_cost_usd": 0.0, "total_calls": 0, "by_model": []}
        conn = sqlite3.connect(str(db_path))
        try:
            cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - window_days * 86400))
            rows = conn.execute(
                "SELECT model, COUNT(*) as calls, COALESCE(SUM(cost_usd),0) as cost "
                "FROM cost_logs WHERE ts >= ? GROUP BY model ORDER BY cost DESC",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()
        by_model = [{"key": r[0] or "unknown", "calls": r[1], "cost_usd": round(r[2], 6)} for r in rows]
        return {
            "total_cost_usd": round(sum(r["cost_usd"] for r in by_model), 6),
            "total_calls": sum(r["calls"] for r in by_model),
            "by_model": by_model,
        }
    except Exception:
        return {"total_cost_usd": 0.0, "total_calls": 0, "by_model": []}


# -- gather: security (already-durable SecurityScanStore) --------------------
def gather_security_summary(db_path: str | Path | None = None, limit: int = 20) -> list[dict]:
    """Most recent run_security_suite verdicts. Fail-soft -> []."""
    try:
        from promptwise.core.security_log import SecurityScanStore
        store = SecurityScanStore(db_path=db_path) if db_path is not None else SecurityScanStore()
        return store.results(limit=limit)
    except Exception:
        return []


# -- gather: governance (project audit chain + governor advisory artifact) ---
def gather_governance_summary(audit_path: str | Path | None = None,
                              proposals_path: str | Path | None = None) -> dict:
    """Audit-chain status + the governor's most recent proposal batch. Both
    inputs are optional paths so this composes cleanly with any repo_root;
    missing files -> zeroed summary, never raises."""
    out = {"audit_records": 0, "chain_ok": True, "governor_actions": []}
    try:
        if audit_path is not None:
            audit_path = Path(audit_path)
            if audit_path.exists():
                from promptwise.core.audit_log import AuditLog
                log = AuditLog(audit_path)
                out["audit_records"] = len(log.records)
                ok, _msg = log.verify()
                out["chain_ok"] = ok
    except Exception:
        pass
    try:
        if proposals_path is not None:
            proposals_path = Path(proposals_path)
            if proposals_path.exists():
                data = json.loads(proposals_path.read_text(encoding="utf-8"))
                out["governor_actions"] = list(data.get("proposals", []))
    except Exception:
        pass
    return out


def gather_report_data(repo_root: str | Path = ".", window_days: int = 30) -> dict:
    """Assemble all three sections, fail-soft per source."""
    root = Path(repo_root)
    try:
        spend = gather_spend_summary(window_days=window_days)
    except Exception:
        spend = {}
    try:
        security = gather_security_summary()
    except Exception:
        security = []
    try:
        governance = gather_governance_summary(
            audit_path=root / ".promptwise" / "audit.jsonl",
            proposals_path=_home_state_dir() / "governor_proposals.json",
        )
    except Exception:
        governance = {}
    return {"spend": spend, "security": security, "governance": governance}


def _home_state_dir() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path().parent
    except Exception:
        return Path.home() / ".promptwise"


# -- pure build: assemble the report dict (no I/O) ----------------------------
def build_report(*, spend: dict, security: list[dict], governance: dict,
                 window_days: int = 30, generated_at: str | None = None) -> dict:
    security = security or []
    scan_count = len(security)
    all_passed = all(bool(s.get("passed", True)) for s in security) if security else True
    return {
        "title": _TITLE,
        "generated_at": generated_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window_days": window_days,
        "spend": {
            "total_cost_usd": round(float(spend.get("total_cost_usd", 0) or 0), 6),
            "total_calls": int(spend.get("total_calls", 0) or 0),
            "by_model": list(spend.get("by_model", []) or []),
        },
        "security": {
            "scan_count": scan_count,
            "all_passed": all_passed,
            "recent": security[:10],
        },
        "governance": {
            "audit_records": int(governance.get("audit_records", 0) or 0),
            "chain_ok": bool(governance.get("chain_ok", True)),
            "governor_actions": list(governance.get("governor_actions", []) or []),
        },
    }


# -- renderers: Markdown / self-contained HTML (no PDF dependency) ------------
def render_markdown(report: dict) -> str:
    sp, sec, gov = report["spend"], report["security"], report["governance"]
    lines = [
        f"# {report['title']}",
        "",
        f"Generated: {report['generated_at']} — window: last {report['window_days']} day(s)",
        "",
        "## Spend",
        f"- Total cost: ${sp['total_cost_usd']:.2f}",
        f"- Total calls: {sp['total_calls']}",
    ]
    for row in sp["by_model"]:
        lines.append(f"  - {row.get('key', 'unknown')}: {row.get('calls', 0)} call(s), ${row.get('cost_usd', 0):.2f}")
    lines += [
        "",
        "## Security scan verdicts",
        f"- Scans recorded: {sec['scan_count']}",
        f"- All passed: {'yes' if sec['all_passed'] else 'no'}",
    ]
    for s in sec["recent"]:
        mark = "PASS" if s.get("passed") else "FAIL"
        lines.append(f"  - [{mark}] {s.get('ts', '')} — {s.get('findings_count', 0)} finding(s)")
    lines += [
        "",
        "## Governance",
        f"- Audit chain records: {gov['audit_records']}",
        f"- Audit chain intact: {'yes' if gov['chain_ok'] else 'NO — needs review'}",
        f"- Governor actions: {len(gov['governor_actions'])}",
    ]
    for a in gov["governor_actions"]:
        lines.append(f"  - {a.get('type', '?')}: {a.get('status', '?')}")
    lines.append("")
    return "\n".join(lines)


def render_html(report: dict) -> str:
    """Self-contained HTML (inline CSS, no external assets/scripts) so it can
    be emailed or dropped anywhere without a build step."""
    md_body = render_markdown(report)
    escaped = _html.escape(md_body)
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
        f"<title>{_html.escape(report['title'])}</title>"
        "<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        "background:#0a0c10;color:#e7e9f0;padding:2rem;line-height:1.5;}"
        "pre{white-space:pre-wrap;font-family:inherit;}</style></head>"
        f"<body><pre>{escaped}</pre></body></html>"
    )


_RENDERERS = {"markdown": render_markdown, "html": render_html}
_EXT = {"markdown": ".md", "html": ".html"}


def write_report(report: dict, path: str | Path, fmt: str = "markdown") -> Path:
    if fmt not in _RENDERERS:
        raise ValueError(f"unknown report format: {fmt!r} (expected one of {sorted(_RENDERERS)})")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_RENDERERS[fmt](report), encoding="utf-8")
    return path


# -- one-shot: gather + build + write (mirrors compliance_export.export_bundle) -
def export_report(*, repo_root: str | Path = ".", window_days: int = 30,
                  out_path: str | Path | None = None, fmt: str = "markdown") -> dict:
    data = gather_report_data(repo_root=repo_root, window_days=window_days)
    report = build_report(spend=data["spend"], security=data["security"],
                          governance=data["governance"], window_days=window_days)
    summary: dict = {"report": report, "written": False}
    if out_path:
        try:
            written = write_report(report, out_path, fmt=fmt)
            summary["written"] = True
            summary["path"] = str(written)
        except Exception as e:
            summary["error"] = f"{type(e).__name__}: {e}"
    return summary
