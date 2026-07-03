"""Ensure this worktree's ``src`` wins over any shared editable install.

Sibling git worktrees share one editable ``promptwise`` install whose ``.pth`` points
at a single checkout, so a bare ``pytest`` here could import another worktree's code.
Prepending this worktree's ``src`` to ``sys.path`` makes tests run against local code.
"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
