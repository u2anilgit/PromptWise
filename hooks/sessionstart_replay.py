#!/usr/bin/env python3
"""Claude Code SessionStart hook — surface the most relevant recent corrections
as context before work begins (push the learning store). Fail-open: any error
exits 0 and the session starts normally."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("sessionstart_replay"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
