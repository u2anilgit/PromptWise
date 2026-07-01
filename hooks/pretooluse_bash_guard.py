#!/usr/bin/env python3
"""Claude Code PreToolUse(Bash) hook — deny destructive shell commands and secret
echoes. Emits a permission deny so it holds even when prompts are skipped.
Fail-open: any error exits 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from promptwise.core.hook_bridge import run
    raise SystemExit(run("pretooluse_bash_guard"))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
