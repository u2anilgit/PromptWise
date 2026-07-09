#!/usr/bin/env python3
"""Claude Code SessionStart hook — generate the periodic org/compliance report
(config/reports.yaml) if it's due. Off by default; fail-open: any error exits 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("scheduled_report_check"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
