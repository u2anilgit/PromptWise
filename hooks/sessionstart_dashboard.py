#!/usr/bin/env python3
"""Claude Code SessionStart hook — auto-launch the PromptWise web dashboard
in the background (detached process) if it isn't already running, and
surface its URL. Fail-open: any error exits 0 and the session starts
normally without a dashboard link."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("sessionstart_dashboard"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
