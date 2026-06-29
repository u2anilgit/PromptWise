#!/usr/bin/env python3
"""Claude Code PostToolUse(Write|Edit) hook — append a hash-chained audit record
for every change (the trace). Advisory only. Fail-open: any error exits 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("posttooluse_audit"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
