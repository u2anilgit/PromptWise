#!/usr/bin/env python3
"""Claude Code PostToolUseFailure / StopFailure hook — fold tool failures and
API-error turn endings into the learning store and audit trail. Fail-open: any
error exits 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("failure_capture"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
