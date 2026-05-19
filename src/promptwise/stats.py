"""Statistics tracking and cost calculation."""

import csv
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from promptwise.config import AppConfig
from promptwise.db import get_db_path
from promptwise.types import StatsSnapshot

CSV_COLUMNS = [
    "id", "ts", "tool", "model", "input_tokens", "cached_input_tokens",
    "output_tokens", "cost_usd", "saving_pct", "metadata_json",
    "duration_ms", "project", "team",
]


class StatsService:
    """Track tool usage and costs."""

    def __init__(self, config: AppConfig, db_path: Optional[Path] = None):
        self.config = config
        self.db_path = get_db_path(db_path)

    async def record(
        self,
        *,
        tool: str,
        model: Optional[str] = None,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        saving_pct: float = 0.0,
        duration_ms: int = 0,
        project: Optional[str] = None,
        team: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Record tool usage."""
        try:
            resolved_model = model or self.config.default_model
            cost = self.calc_cost(
                resolved_model,
                input_tokens,
                output_tokens,
                cached_input_tokens,
                "standard",
                self.config.pricing.models,
            )

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO history
                    (ts, tool, model, input_tokens, cached_input_tokens,
                     output_tokens, cost_usd, saving_pct, metadata_json,
                     duration_ms, project, team)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        tool,
                        resolved_model,
                        input_tokens,
                        cached_input_tokens,
                        output_tokens,
                        cost,
                        saving_pct,
                        json.dumps(metadata or {}),
                        duration_ms,
                        project,
                        team,
                    ),
                )
                await db.commit()
        except Exception as e:
            print(f"Stats record failed: {e}", file=sys.stderr)

    async def snapshot(self, since: Optional[str] = None) -> StatsSnapshot:
        """Get statistics snapshot."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM history"
            params = []

            if since:
                query += " WHERE ts >= ?"
                params.append(since)

            query += " ORDER BY ts"

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()

            if not rows:
                return StatsSnapshot(
                    total_calls=0,
                    total_input_tokens=0,
                    total_cached_input_tokens=0,
                    total_output_tokens=0,
                    total_cost_usd=0.0,
                    cost_by_model={},
                    calls_by_tool={},
                    avg_saving_pct=0.0,
                    cache_hit_rate=0.0,
                    total_duration_ms=0,
                    since=since,
                )

            total_calls = len(rows)
            total_input_tokens = sum(r["input_tokens"] or 0 for r in rows)
            total_cached_input_tokens = sum(r["cached_input_tokens"] or 0 for r in rows)
            total_output_tokens = sum(r["output_tokens"] or 0 for r in rows)
            total_cost_usd = sum(r["cost_usd"] or 0.0 for r in rows)
            total_duration_ms = sum(r["duration_ms"] or 0 for r in rows)

            cost_by_model: dict[str, float] = {}
            calls_by_tool: dict[str, int] = {}
            calls_by_model: dict[str, int] = {}
            tokens_by_model: dict[str, int] = {}

            for row in rows:
                model = row["model"]
                tool = row["tool"]
                cost = row["cost_usd"] or 0.0
                tokens = (row["input_tokens"] or 0) + (row["output_tokens"] or 0)

                if model:
                    cost_by_model[model] = cost_by_model.get(model, 0.0) + cost
                    calls_by_model[model] = calls_by_model.get(model, 0) + 1
                    tokens_by_model[model] = tokens_by_model.get(model, 0) + tokens

                calls_by_tool[tool] = calls_by_tool.get(tool, 0) + 1

            saving_pcts = [r["saving_pct"] for r in rows if r["saving_pct"]]
            avg_saving_pct = (
                sum(saving_pcts) / len(saving_pcts) if saving_pcts else 0.0
            )

            cache_hit_rate = (
                total_cached_input_tokens / total_input_tokens
                if total_input_tokens > 0
                else 0.0
            )

            return StatsSnapshot(
                total_calls=total_calls,
                total_input_tokens=total_input_tokens,
                total_cached_input_tokens=total_cached_input_tokens,
                total_output_tokens=total_output_tokens,
                total_cost_usd=round(total_cost_usd, 6),
                cost_by_model=cost_by_model,
                calls_by_tool=calls_by_tool,
                calls_by_model=calls_by_model,
                tokens_by_model=tokens_by_model,
                avg_saving_pct=avg_saving_pct,
                cache_hit_rate=cache_hit_rate,
                total_duration_ms=total_duration_ms,
                since=since,
            )

    async def clear(self) -> None:
        """Clear all history (test cleanup)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM history")
            await db.commit()

    async def clear_old(self, older_than_days: int) -> int:
        """Delete history records older than N days. Returns count deleted."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=older_than_days)
        ).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM history WHERE ts < ?", (cutoff,)
            )
            await db.commit()
            return cursor.rowcount

    async def export(
        self, since: Optional[str] = None, format: str = "json"
    ) -> str:
        """Export history as JSON array or CSV string."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM history"
            params = []
            if since:
                query += " WHERE ts >= ?"
                params.append(since)
            query += " ORDER BY ts"
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()

        records = [dict(row) for row in rows]

        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=CSV_COLUMNS,
                extrasaction="ignore",
            )
            writer.writeheader()
            if records:
                writer.writerows(records)
            return output.getvalue()

        return json.dumps(records)

    @staticmethod
    def calc_cost(
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int,
        mode: str,
        pricing_models: dict,
    ) -> float:
        """Calculate cost for request."""
        model_config = pricing_models.get(model)
        if not model_config:
            return 0.0

        rates = model_config.rates

        if mode == "batch":
            input_rate = rates.batch_input_per_mtok / 1_000_000
            output_rate = rates.batch_output_per_mtok / 1_000_000
        else:
            input_rate = rates.input_per_mtok / 1_000_000
            output_rate = rates.output_per_mtok / 1_000_000
            cache_hit_rate = rates.cache_hit_per_mtok / 1_000_000

            uncached_input = input_tokens - cached_input_tokens
            return round(
                uncached_input * input_rate
                + cached_input_tokens * cache_hit_rate
                + output_tokens * output_rate,
                6,
            )

        return round(
            input_tokens * input_rate + output_tokens * output_rate,
            6,
        )
