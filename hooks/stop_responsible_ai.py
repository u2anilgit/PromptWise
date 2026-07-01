#!/usr/bin/env python3
"""Claude Code Stop hook — advisory responsible-AI scan (grounding, bias, ethics)
over the turn's response, if present. Warn-only; never blocks. Fail-open: any
error exits 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("responsible_ai_check"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
