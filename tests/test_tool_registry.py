"""Handler-registry coverage (Phase F decorator registry, extending Phase 10 WP10.1).

Guards the tool registry from a dispatch gap: every advertised tool name
(_TOOL_DEFS) must have a handler in _HANDLERS, and every handler must map to an
advertised tool (no orphan handler). Both are now derived from ToolRegistry's
@tool-decorated entries rather than hand-synced literals. Also verifies an
unknown name preserves the exact legacy fallback behavior.
"""
import asyncio
import inspect
import json
import typing

import promptwise.server as s

ADVERTISED = {t.name for t in s._TOOL_DEFS}
REGISTERED = set(s._HANDLERS)


def test_every_advertised_tool_has_a_handler():
    missing = sorted(ADVERTISED - REGISTERED)
    assert not missing, f"advertised tools with no handler: {missing}"


def test_no_orphan_handlers():
    orphans = sorted(REGISTERED - ADVERTISED)
    assert not orphans, f"handlers with no advertised tool: {orphans}"


def test_registry_is_exact_bijection():
    assert REGISTERED == ADVERTISED


def test_handlers_are_coroutine_functions():
    for name, fn in s._HANDLERS.items():
        assert inspect.iscoroutinefunction(fn), name


def test_unknown_tool_preserves_legacy_fallback():
    # None stands in for ctx: the unknown-tool fallback path never reads it.
    ctx = typing.cast(s.ServerContext, None)
    out = json.loads(asyncio.run(s.call_tool(ctx, "does_not_exist", {})))
    assert out == {"error": "Unknown tool: does_not_exist",
                   "type": "UnknownTool", "tool": "does_not_exist"}
