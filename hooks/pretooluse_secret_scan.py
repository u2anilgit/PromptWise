#!/usr/bin/env python3
"""Claude Code PreToolUse(Write|Edit) hook — block writes that trip the secret /
destructive / injection scanner. Fail-open: any error exits 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("pretooluse_scan"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
