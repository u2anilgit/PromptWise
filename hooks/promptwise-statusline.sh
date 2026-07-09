#!/usr/bin/env bash
# PromptWise statusline badge (POSIX) — prints "budget: N% used | last scan: <ago>".
# Works whether or not the package is pip-installed: sets PYTHONPATH relative
# to this script (same convention hooks/*.py already use) and invokes the
# core module directly. Fails silently (prints nothing) rather than wedging
# a shell prompt if the plugin isn't bootstrapped yet.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -n "${PYTHONPATH:-}" ]; then
  export PYTHONPATH="$ROOT/src:$PYTHONPATH"
else
  export PYTHONPATH="$ROOT/src"
fi
python3 -m promptwise.core.statusline 2>/dev/null || python -m promptwise.core.statusline 2>/dev/null
