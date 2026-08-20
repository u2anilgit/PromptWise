"""Tests for the optional domain tag on @tool / ToolRegistry.tools_by_domain().

Uses a fresh ToolRegistry() instance (not the module-level singleton) so
these tests never touch the real 116-tool registry. Registration happens
as the decorator's own side effect (ToolRegistry.tool(...) both builds
the Tool and stores the entry) -- there is no separate .register() call
in the real API, unlike the plan brief's placeholder sketch.
"""
from promptwise.core.tool_registry import ToolRegistry

_SCHEMA = {"type": "object", "properties": {}}


def test_tool_decorator_defaults_domain_to_general():
    registry = ToolRegistry()

    @registry.tool(name="_test_tool_a", description="test", schema=_SCHEMA)
    async def _handler(ctx, arguments):
        return "ok"

    assert registry.tools_by_domain().get("general") == ["_test_tool_a"]


def test_tool_decorator_accepts_explicit_domain():
    registry = ToolRegistry()

    @registry.tool(name="_test_tool_b", description="test", schema=_SCHEMA, domain="security")
    async def _handler(ctx, arguments):
        return "ok"

    assert registry.tools_by_domain().get("security") == ["_test_tool_b"]
