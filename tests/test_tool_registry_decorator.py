"""Unit tests for the Phase F decorator-based tool registry (ToolRegistry).

Each test builds a throwaway ToolRegistry() instance so guard behavior is
verified in isolation from the module-level registry that (after Task 3)
holds all 90 production tools.
"""
import typing

import pytest

from promptwise.server import ToolRegistry


def test_register_adds_tool_and_handler():
    registry = ToolRegistry()

    @registry.tool(name="ping", description="ping", schema={"type": "object", "properties": {}})
    async def _handle_ping(ctx, arguments):
        return "pong"

    assert "ping" in registry.entries
    entry = registry.entries["ping"]
    assert entry.tool.name == "ping"
    assert entry.tool.description == "ping"
    assert entry.tool.inputSchema == {"type": "object", "properties": {}}
    assert entry.handler is _handle_ping


def test_duplicate_name_raises():
    registry = ToolRegistry()

    @registry.tool(name="dup", description="first", schema={"type": "object"})
    async def _handle_first(ctx, arguments):
        return "first"

    with pytest.raises(ValueError, match="duplicate tool registration"):
        @registry.tool(name="dup", description="second", schema={"type": "object"})
        async def _handle_second(ctx, arguments):
            return "second"


def test_non_coroutine_handler_raises():
    registry = ToolRegistry()

    with pytest.raises(TypeError, match="coroutine function"):
        @registry.tool(name="sync_tool", description="x", schema={"type": "object"})
        def _handle_sync(ctx, arguments):
            return "nope"


def test_non_object_schema_raises():
    registry = ToolRegistry()

    with pytest.raises(TypeError, match="object-type inputSchema"):
        @registry.tool(name="bad_schema", description="x", schema={"type": "array"})
        async def _handle_bad(ctx, arguments):
            return "nope"


def test_non_dict_schema_raises():
    registry = ToolRegistry()

    with pytest.raises(TypeError, match="object-type inputSchema"):
        # Intentional bad input: verifies the decorator's isinstance guard
        # rejects a non-dict schema at registration time.
        @registry.tool(name="not_a_dict", description="x", schema=typing.cast(dict, "oops"))
        async def _handle_not_dict(ctx, arguments):
            return "nope"
