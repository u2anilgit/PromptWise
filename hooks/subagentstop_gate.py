#!/usr/bin/env python3
"""Claude Code SubagentStop hook — run the advisory quality gate and record an
audit entry so sub-agent work is governed like the main loop. Fail-open: any
error exits 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("subagentstop_gate"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
