#!/usr/bin/env python3
"""Claude Code Stop hook — advisory quality-gate decision at end of turn. Never
blocks. Fail-open: any error exits 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("stop_quality_gate"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
