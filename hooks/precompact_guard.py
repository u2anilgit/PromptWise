#!/usr/bin/env python3
"""Claude Code PreCompact hook — inject a note preserving governance state (audit
chain + files under audit) so it survives compaction. Fail-open: any error exits
0 and compaction proceeds normally."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("precompact_guard"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
