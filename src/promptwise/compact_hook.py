"""Claude Code PostToolUse hook — warns when estimated context approaches threshold.

Wire in settings.json:
  "hooks": {"PostToolUse": [{"matcher": ".*", "hooks": [
    {"type": "command", "command": "python -m promptwise.compact_hook"}
  ]}]}

Reads stdin (hook JSON, unused), queries PromptWise DB for cumulative tool-call
tokens as a proxy for conversation size, prints warning if near threshold.
Accurate compaction requires calling auto_compact with full turns.
"""

import asyncio
import sys
from pathlib import Path

import aiosqlite

from promptwise.db import get_db_path

WARN_RATIO = 0.80  # warn at 80% of threshold_tokens


def should_warn(current_tokens: int, threshold_tokens: int) -> bool:
    return current_tokens > int(threshold_tokens * WARN_RATIO)


async def _get_recent_token_total(db_path: Path) -> int:
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) FROM history"
            )
            row = await cursor.fetchone()
            await cursor.close()
            return int(row[0]) if row else 0
    except Exception:
        return 0


def main() -> None:
    sys.stdin.read()  # consume hook JSON (unused)

    db_path = get_db_path()
    total = asyncio.run(_get_recent_token_total(db_path))

    threshold_tokens = 50000  # default; override via promptwise.yaml if needed
    if should_warn(total, threshold_tokens):
        pct = int(total / threshold_tokens * 100)
        print(
            f"⚠️  PromptWise: estimated context at {total:,} tokens "
            f"({pct}% of threshold). Call auto_compact with full turns for accurate check.",
            flush=True,
        )


if __name__ == "__main__":
    main()
