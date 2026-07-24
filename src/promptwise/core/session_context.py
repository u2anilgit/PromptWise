"""session_context -- a stable per-process session identity.

One MCP server process == one Claude Code session (confirmed convention,
see hook_bridge.py's own docstring). Before this module existed, every
MemoryManager.record_cost() call site hardcoded session_id="default",
collapsing all cost history into one bucket regardless of how many real
sessions ran -- making a session-grouped rollup meaningless. This constant
gives each process run a real, distinct identity to stamp instead.
"""
from __future__ import annotations

import uuid

CURRENT_SESSION_ID: str = uuid.uuid4().hex
