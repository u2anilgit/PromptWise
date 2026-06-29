#!/usr/bin/env python3
"""Claude Code PreToolUse(any) hook — per-session tool-call ceiling to curb
runaway loops. Fail-open: any error exits 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("tool_call_budget"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
