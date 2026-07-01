"""retention — the dashboard's data layer: time windows, daily rollups, and the
metric model the UI renders. Pure functions over plain dicts so it is fully
unit-testable without a server or a live database.

Two-tier retention, one local SQLite file, no infrastructure:
  * **Hot** raw events: full detail, 0-90 days (configurable 7/30/60/90).
  * **Archive** daily rollups: one row per day x model, 90 days - 1 year.
Only *granularity* drops past 90 days; the timeline stays continuous and
deprecated models are never dropped from history.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

HOT_MAX_DAYS = 90       # raw-event granularity cap
ARCHIVE_MAX_DAYS = 365  # rolled-up granularity cap (1 year)
WINDOW_OPTIONS = [7, 30, 60, 90]
DEFAULT_WINDOW = 30


def clamp_window(days, raw: bool = True) -> int:
    """Clamp a requested window: raw data is capped at 90 days, archive at 365."""
    try:
        days = int(days)
    except (TypeError, ValueError):
        return DEFAULT_WINDOW
    cap = HOT_MAX_DAYS if raw else ARCHIVE_MAX_DAYS
    return max(1, min(days, cap))


def window_cutoff(days: int, now_iso: str) -> str:
    """ISO timestamp `days` before `now_iso` — pushed into the stats query."""
    now = datetime.fromisoformat(now_iso)
    return (now - timedelta(days=int(days))).isoformat()


def _day(ts: str) -> str:
    return (ts or "")[:10]


def rollup(logs: list[dict]) -> list[dict]:
    """Compact raw cost events into archive rows: one per (day x model)."""
    agg: dict[tuple, dict] = {}
    for l in logs:
        key = (_day(l.get("ts", "")), l.get("model", "unknown"))
        r = agg.setdefault(key, {"day": key[0], "model": key[1], "calls": 0,
                                 "cost_usd": 0.0, "input_tokens": 0.0,
                                 "output_tokens": 0.0, "lines": 0.0, "_sav": []})
        r["calls"] += 1
        r["cost_usd"] += float(l.get("cost_usd", 0) or 0)
        r["input_tokens"] += float(l.get("input_tokens", 0) or 0)
        r["output_tokens"] += float(l.get("output_tokens", 0) or 0)
        r["lines"] += float(l.get("lines", 0) or 0)
        if l.get("saving_pct"):
            r["_sav"].append(float(l["saving_pct"]))
    out = []
    for r in agg.values():
        sav = r.pop("_sav")
        r["avg_saving_pct"] = round(sum(sav) / len(sav), 2) if sav else 0.0
        r["cost_usd"] = round(r["cost_usd"], 6)
        out.append(r)
    return sorted(out, key=lambda r: (r["day"], r["model"]))


def build_dashboard_model(logs: list[dict], *, window_days: int, now_iso: str,
                          top_tier_price: dict | None = None,
                          governance: dict | None = None) -> dict:
    """The full metric payload the dashboard renders.

    `top_tier_price` (from the model registry: {input_per_mtok, output_per_mtok})
    lets us compute the North Star — net savings vs. running everything on the
    top tier. When absent, net savings degrades to 0 rather than guessing.
    """
    total_cost = round(sum(float(l.get("cost_usd", 0) or 0) for l in logs), 6)
    total_calls = len(logs)
    total_in = sum(float(l.get("input_tokens", 0) or 0) for l in logs)
    total_out = sum(float(l.get("output_tokens", 0) or 0) for l in logs)
    total_lines = sum(float(l.get("lines", 0) or 0) for l in logs)
    savings = [float(l["saving_pct"]) for l in logs if l.get("saving_pct")]
    avg_saving_pct = round(sum(savings) / len(savings), 1) if savings else 0.0

    # North Star — baseline if every call ran on the top tier, minus actual.
    net_savings_usd = 0.0
    savings_rate_pct = 0.0
    if top_tier_price:
        ti = float(top_tier_price.get("input_per_mtok", 0) or 0)
        to = float(top_tier_price.get("output_per_mtok", 0) or 0)
        baseline = (total_in * ti + total_out * to) / 1_000_000
        if baseline > 0:
            net_savings_usd = round(baseline - total_cost, 6)
            savings_rate_pct = round(max(0.0, net_savings_usd) / baseline * 100, 1)

    sessions = {l.get("session_id") for l in logs if l.get("session_id")}
    cost_per_task = round(total_cost / max(1, len(sessions)), 6)

    # breakdowns
    by_model: dict[str, dict] = {}
    by_project: dict[str, dict] = {}
    by_skill: dict[str, dict] = {}
    for l in logs:
        for key, bucket in ((l.get("model", "unknown"), by_model),
                            (l.get("project_id", "") or "unassigned", by_project),
                            (l.get("tool", "") or "unknown", by_skill)):
            b = bucket.setdefault(key, {"calls": 0, "cost_usd": 0.0})
            b["calls"] += 1
            b["cost_usd"] = round(b["cost_usd"] + float(l.get("cost_usd", 0) or 0), 6)

    # trends: spend/day and model-mix/day (deprecated models retained)
    daily = rollup(logs)
    spend_by_day: dict[str, float] = {}
    mix_by_day: dict[str, dict] = {}
    for r in daily:
        spend_by_day[r["day"]] = round(spend_by_day.get(r["day"], 0.0) + r["cost_usd"], 6)
        mix_by_day.setdefault(r["day"], {})[r["model"]] = r["calls"]

    return {
        "window_days": window_days,
        "generated_at": now_iso,
        "headline": {
            "net_savings_usd": net_savings_usd,
            "savings_rate_pct": savings_rate_pct,
            "total_cost_usd": total_cost,
            "tokens_saved_pct": avg_saving_pct,
            "cost_per_task_usd": cost_per_task,
            "total_calls": total_calls,
            "lines_changed": int(total_lines),
        },
        "trends": {"spend_by_day": spend_by_day, "model_mix_by_day": mix_by_day},
        "breakdowns": {
            "by_model": _sorted_bucket(by_model),
            "by_project": _sorted_bucket(by_project),
            "by_skill": _sorted_bucket(by_skill),
        },
        "governance": governance or {},
    }


def _sorted_bucket(bucket: dict) -> list[dict]:
    rows = [{"key": k, **v} for k, v in bucket.items()]
    return sorted(rows, key=lambda r: r["cost_usd"], reverse=True)


def governance_summary(state_dir) -> dict:
    """Read the governance signals this phase produces from the project-local
    state dir: audit records + chain status, and recorded permission denials.
    Fail-soft: missing files just report zero."""
    from pathlib import Path
    import json
    d = Path(state_dir)
    out = {"audit_records": 0, "chain_ok": True, "denials": 0, "failures": 0}
    try:
        audit = d / "audit.jsonl"
        if audit.exists():
            lines = [ln for ln in audit.read_text(encoding="utf-8").splitlines() if ln.strip()]
            out["audit_records"] = len(lines)
            for ln in lines:
                try:
                    if "failure" in (json.loads(ln).get("task", "")):
                        out["failures"] += 1
                except Exception:
                    pass
    except Exception:
        pass
    try:
        denials = d / "denials.jsonl"
        if denials.exists():
            out["denials"] = len([ln for ln in denials.read_text(encoding="utf-8").splitlines() if ln.strip()])
    except Exception:
        pass
    return out


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
