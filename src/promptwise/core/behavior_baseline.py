"""behavior_baseline -- per-actor statistical behavior baselines built from
data already collected in this project (SQLite cost_logs + the audit
JSONL). Pure stdlib statistics (median absolute deviation, frequency
tables) -- no ML, no new dependencies. Feeds core/anomaly_detector.py's
drift comparison.
"""
from __future__ import annotations

import json
import sqlite3
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        return Path.home() / ".promptwise" / "promptwise.db"


@dataclass
class BehaviorStats:
    actor: str
    window_days: int
    prompt_length_median: float = 0.0
    prompt_length_mad: float = 0.0
    tool_bigram_freq: dict = field(default_factory=dict)
    model_tier_mix: dict = field(default_factory=dict)
    hourly_histogram: dict = field(default_factory=dict)
    distinct_files_touched: int = 0
    computed_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class BaselineStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else _default_db()
        if str(self.db_path) != ":memory:":
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
                """CREATE TABLE IF NOT EXISTS behavior_baselines (
                       actor       TEXT NOT NULL,
                       metric      TEXT NOT NULL,
                       window_days INTEGER NOT NULL,
                       stats_json  TEXT NOT NULL,
                       computed_at TEXT NOT NULL,
                       PRIMARY KEY (actor, metric, window_days)
                   )""")
            conn.commit()
        finally:
            conn.close()

    def save(self, actor: str, metric: str, window_days: int, stats: dict, computed_at: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO behavior_baselines (actor, metric, window_days, stats_json, computed_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(actor, metric, window_days) DO UPDATE SET "
                "stats_json = excluded.stats_json, computed_at = excluded.computed_at",
                (actor, metric, window_days, json.dumps(stats), computed_at))
            conn.commit()
        finally:
            conn.close()

    def load(self, actor: str, metric: str, window_days: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM behavior_baselines WHERE actor = ? AND metric = ? AND window_days = ?",
                (actor, metric, window_days)).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return {"actor": row["actor"], "metric": row["metric"], "window_days": row["window_days"],
                "stats_json": json.loads(row["stats_json"]), "computed_at": row["computed_at"]}

    def list_all(self, actor: str | None = None) -> list[dict]:
        conn = self._connect()
        try:
            if actor:
                rows = conn.execute(
                    "SELECT * FROM behavior_baselines WHERE actor = ?", (actor,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM behavior_baselines").fetchall()
        finally:
            conn.close()
        return [{"actor": r["actor"], "metric": r["metric"], "window_days": r["window_days"],
                 "stats_json": json.loads(r["stats_json"]), "computed_at": r["computed_at"]} for r in rows]


def _mad(values: list[float]) -> float:
    if not values:
        return 0.0
    med = statistics.median(values)
    return statistics.median([abs(v - med) for v in values])


def compute_baseline(
    actor: str, *, window_days: int = 30,
    cost_logs: list[dict] | None = None, audit_records: list[dict] | None = None,
) -> BehaviorStats:
    """Build a BehaviorStats snapshot for `actor` from already-collected
    telemetry. Pass `cost_logs`/`audit_records` explicitly for testability;
    when omitted, this fetches them itself (cost_logs via
    MemoryManager.raw_cost_logs, audit_records via a fresh AuditLog().query())."""
    if cost_logs is None:
        import asyncio
        from promptwise.db.models import MemoryManager
        cost_logs = asyncio.run(MemoryManager().raw_cost_logs())
    if audit_records is None:
        from promptwise.core.audit_log import AuditLog
        audit_records = AuditLog().query()

    lengths = [float(r.get("input_tokens", 0.0)) for r in cost_logs]
    tools_in_order = [r.get("tool", "") for r in cost_logs if r.get("tool")]
    bigrams: Counter = Counter()
    for a, b in zip(tools_in_order, tools_in_order[1:]):
        bigrams[f"{a}->{b}"] += 1

    model_counts: Counter = Counter(r.get("model", "") for r in cost_logs if r.get("model"))
    total_models = sum(model_counts.values())
    model_mix = {m: c / total_models for m, c in model_counts.items()} if total_models else {}

    hourly: Counter = Counter()
    for r in cost_logs:
        ts = r.get("ts", "")
        if len(ts) >= 13 and ts[10] == "T":
            hourly[ts[11:13]] += 1

    files: set[str] = set()
    for rec in audit_records:
        if rec.get("actor") == actor:
            files.update(rec.get("files_touched", []) or [])

    return BehaviorStats(
        actor=actor, window_days=window_days,
        prompt_length_median=statistics.median(lengths) if lengths else 0.0,
        prompt_length_mad=_mad(lengths),
        tool_bigram_freq=dict(bigrams), model_tier_mix=model_mix,
        hourly_histogram=dict(hourly), distinct_files_touched=len(files),
    )
