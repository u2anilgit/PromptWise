"""session_context -- a per-connection session identity.

Was a process-global constant (one MCP server process == one Claude Code
session, stdio's original convention). That assumption breaks once one
process can serve multiple concurrent remote HTTP connections (see
docs/superpowers/specs/2026-09-01-remote-mcp-transport-design.md) --
two connections sharing one session_id would corrupt cost/audit rollups
across unrelated clients.

get_current_session_id() now reads a contextvars.ContextVar, so each
async task (each stdio process's single implicit task, or each HTTP
connection's own task) sees its own value without leaking into siblings
-- see test_session_context.py's concurrency test for the property this
exists to guarantee. Default (no explicit set_current_session_id call,
e.g. stdio's normal path) is a single value generated once at import
time, matching the old constant's exact behavior for every existing
caller.
"""
from __future__ import annotations

import contextvars
import uuid

_default_session_id = uuid.uuid4().hex
_session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "promptwise_session_id", default=_default_session_id
)


def get_current_session_id() -> str:
    """The active session_id for the current async context. Stdio (no
    explicit set call) returns the same process-wide value every time,
    identical to the old CURRENT_SESSION_ID constant's behavior."""
    return _session_id_var.get()


def set_current_session_id(value: str) -> contextvars.Token:
    """Set the session_id for the current async context (e.g. once per
    incoming HTTP connection, before dispatching any tool calls on it).
    Returns a token for reset_current_session_id."""
    return _session_id_var.set(value)


def reset_current_session_id(token: contextvars.Token) -> None:
    """Restore the previous session_id -- call in a finally block after
    set_current_session_id, mirroring contextvars.ContextVar.reset's own
    contract."""
    _session_id_var.reset(token)
