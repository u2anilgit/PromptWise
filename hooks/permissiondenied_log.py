#!/usr/bin/env python3
"""Claude Code PermissionDenied hook — record the denial as telemetry so the
permission tuner can learn allow/deny rules later. Never blocks. Fail-open."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("permissiondenied_log"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
