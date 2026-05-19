"""CLI entry point for PromptWise."""

import asyncio
import subprocess
import sys
from pathlib import Path

from promptwise.config import load_config
from promptwise.db import init_db
from promptwise.stats import StatsService


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2 or sys.argv[1] == "serve":
        _serve()
    elif sys.argv[1] == "stats":
        _stats()
    elif sys.argv[1] == "eval":
        _evaluate()
    elif sys.argv[1] == "reload":
        print("Restart server to reload config")
    else:
        print(f"Unknown command: {sys.argv[1]}")
        print("Commands: serve (default), stats, eval, reload")


def _serve() -> None:
    """Run MCP server."""
    subprocess.run(
        [sys.executable, "-m", "promptwise.server"],
        check=False,
    )


def _stats() -> None:
    """Print session statistics."""
    config = load_config()
    db_path = Path.home() / ".promptwise" / "history.db"

    stats = StatsService(config, db_path)

    snapshot = asyncio.run(stats.snapshot())

    print(f"Total calls: {snapshot.total_calls}")
    print(f"Total cost: ${snapshot.total_cost_usd:.6f}")
    print(f"Avg saving: {snapshot.avg_saving_pct:.1f}%")
    print(f"Cache hit rate: {snapshot.cache_hit_rate:.1%}")
    print(f"Calls by tool: {snapshot.calls_by_tool}")


def _evaluate() -> None:
    """Run evaluation report."""
    config = load_config()
    db_path = Path.home() / ".promptwise" / "history.db"

    stats = StatsService(config, db_path)

    from promptwise.evaluator import Evaluator

    evaluator = Evaluator(config, stats)
    report = asyncio.run(evaluator.report())

    print(f"Total rewrites: {report.get('total_rewrites', 0)}")
    print(
        f"Avg length delta: {report.get('avg_length_delta', 0):.1%}"
    )
    print(
        f"Suspicious rate: {report.get('suspicious_rate', 0):.1%}"
    )
    print(
        f"Median saving: {report.get('median_saving_pct', 0):.1f}%"
    )


if __name__ == "__main__":
    main()
