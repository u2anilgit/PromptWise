"""
Tests for MCPAdapter (MCP/Claude Code transport).
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from promptwise_v2.transports import ToolRequest, ToolResponse
from promptwise_v2.transports.mcp_adapter import MCPAdapter


@pytest.fixture
def mcp_adapter():
    """Create MCPAdapter instance."""
    return MCPAdapter()


@pytest.fixture
def mock_server_context():
    """Create mock ServerContextV2."""
    context = Mock()
    context.session_id = "test-session"
    context.session_budget = 1.0
    context.preferred_model = "claude-sonnet-4-6"
    context.version = "2.0.0"
    return context


@pytest.fixture
def mock_call_tool_func():
    """Create mock call_tool_v2 function."""
    async def call_tool(ctx, tool_name, params):
        if tool_name == "get_session_stats":
            return {
                "total_calls": 1,
                "total_cost_usd": 0.01,
                "model_distribution": {"claude-sonnet-4-6": 1}
            }
        elif tool_name == "route_request":
            return {
                "recommended_model": "claude-sonnet-4-6",
                "reason": "Test routing"
            }
        elif tool_name == "invalid_tool":
            raise ValueError("Tool not found: invalid_tool")
        elif tool_name == "error_tool":
            raise RuntimeError("Unexpected error")
        return {"result": "success"}

    return call_tool


class TestMCPAdapterInitialization:
    """Test MCPAdapter initialization."""

    def test_init(self, mcp_adapter):
        """Test adapter initialization."""
        assert mcp_adapter.name == "mcp"
        assert mcp_adapter.server_context is None
        assert mcp_adapter.call_tool_func is None

    def test_set_server(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test setting server context."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)
        assert mcp_adapter.server_context == mock_server_context
        assert mcp_adapter.call_tool_func == mock_call_tool_func


class TestMCPAdapterToolCalls:
    """Test MCPAdapter tool execution."""

    @pytest.mark.asyncio
    async def test_call_tool_success(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test successful tool call."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)

        request = ToolRequest(
            tool_name="get_session_stats",
            params={},
            session_id="test-session"
        )

        response = await mcp_adapter.call_tool(request)

        assert response.success
        assert response.error is None
        assert "total_cost_usd" in response.result
        assert response.metadata["adapter"] == "mcp"

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test calling non-existent tool."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)

        request = ToolRequest(
            tool_name="invalid_tool",
            params={},
            session_id="test-session"
        )

        response = await mcp_adapter.call_tool(request)

        assert not response.success
        assert "not found" in response.error.lower()
        assert response.metadata["error_type"] == "not_found"

    @pytest.mark.asyncio
    async def test_call_tool_error(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test tool execution error."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)

        request = ToolRequest(
            tool_name="error_tool",
            params={},
            session_id="test-session"
        )

        response = await mcp_adapter.call_tool(request)

        assert not response.success
        assert "RuntimeError" in response.error
        assert response.metadata["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_call_tool_not_initialized(self, mcp_adapter):
        """Test calling tool when adapter not initialized."""
        request = ToolRequest(
            tool_name="get_session_stats",
            params={},
            session_id="test-session"
        )

        response = await mcp_adapter.call_tool(request)

        assert not response.success
        assert "not properly initialized" in response.error.lower()

    @pytest.mark.asyncio
    async def test_call_tool_with_context(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test tool call with session context."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)

        context = {
            "budget": 0.50,
            "model": "claude-haiku-4-5",
            "auto_role": True
        }

        request = ToolRequest(
            tool_name="route_request",
            params={"text": "test"},
            session_id="test-session",
            context=context
        )

        response = await mcp_adapter.call_tool(request)

        assert response.success
        # Verify context was stored
        stored_context = mcp_adapter.get_session_context("test-session")
        assert stored_context["budget"] == 0.50
        assert stored_context["model"] == "claude-haiku-4-5"


class TestMCPAdapterSessionContext:
    """Test session context management."""

    def test_set_session_context(self, mcp_adapter):
        """Test setting session context."""
        context = {"budget": 0.50, "model": "claude-opus-4-7"}
        mcp_adapter.set_session_context("session-1", context)

        stored = mcp_adapter.get_session_context("session-1")
        assert stored["budget"] == 0.50
        assert stored["model"] == "claude-opus-4-7"

    def test_get_missing_session_context(self, mcp_adapter):
        """Test retrieving non-existent session context."""
        stored = mcp_adapter.get_session_context("non-existent")
        assert stored == {}

    def test_set_session_context_on_server(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test setting context propagates to server."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)

        context = {
            "budget": 0.75,
            "model": "claude-haiku-4-5"
        }

        mcp_adapter.set_session_context_on_server("session-1", context)

        assert mock_server_context.session_budget == 0.75
        assert mock_server_context.preferred_model == "claude-haiku-4-5"


class TestMCPAdapterLifecycle:
    """Test adapter lifecycle hooks."""

    def test_start(self, mcp_adapter):
        """Test adapter start."""
        # Should not raise
        mcp_adapter.start()

    def test_stop(self, mcp_adapter):
        """Test adapter stop."""
        # Should not raise
        mcp_adapter.stop()

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self, mcp_adapter):
        """Test health check when not initialized."""
        result = await mcp_adapter.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_success(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test successful health check."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)
        result = await mcp_adapter.health_check()
        assert result is True


class TestMCPAdapterExecutionTime:
    """Test execution time tracking."""

    @pytest.mark.asyncio
    async def test_execution_time_recorded(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test that execution time is tracked."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)

        request = ToolRequest(
            tool_name="get_session_stats",
            params={},
            session_id="test-session"
        )

        response = await mcp_adapter.call_tool(request)

        assert response.execution_ms >= 0
        assert isinstance(response.execution_ms, int)


class TestMCPAdapterMetadata:
    """Test response metadata."""

    @pytest.mark.asyncio
    async def test_metadata_includes_adapter_name(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test that metadata includes adapter name."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)

        request = ToolRequest(
            tool_name="get_session_stats",
            params={},
            session_id="test-session"
        )

        response = await mcp_adapter.call_tool(request)

        assert response.metadata["adapter"] == "mcp"
        assert "server_version" in response.metadata

    @pytest.mark.asyncio
    async def test_metadata_includes_error_type_on_failure(self, mcp_adapter, mock_server_context, mock_call_tool_func):
        """Test that metadata includes error type on failure."""
        mcp_adapter.set_server(mock_server_context, mock_call_tool_func)

        request = ToolRequest(
            tool_name="error_tool",
            params={},
            session_id="test-session"
        )

        response = await mcp_adapter.call_tool(request)

        assert response.metadata["error_type"] == "RuntimeError"


class TestToolRequestValidation:
    """Test ToolRequest validation."""

    def test_tool_request_missing_name(self):
        """Test ToolRequest requires tool_name."""
        with pytest.raises(ValueError):
            ToolRequest(tool_name="", params={}, session_id="session-1")

    def test_tool_request_missing_session_id(self):
        """Test ToolRequest requires session_id."""
        with pytest.raises(ValueError):
            ToolRequest(tool_name="get_stats", params={}, session_id="")

    def test_tool_request_invalid_params(self):
        """Test ToolRequest requires dict params."""
        with pytest.raises(ValueError):
            ToolRequest(tool_name="get_stats", params="invalid", session_id="session-1")

    def test_tool_request_valid(self):
        """Test valid ToolRequest creation."""
        request = ToolRequest(
            tool_name="get_stats",
            params={"key": "value"},
            session_id="session-1"
        )
        assert request.tool_name == "get_stats"
        assert request.params["key"] == "value"


class TestToolResponseValidation:
    """Test ToolResponse validation."""

    def test_tool_response_success(self):
        """Test successful response."""
        response = ToolResponse(result={"key": "value"})
        assert response.success
        assert response.error is None

    def test_tool_response_error(self):
        """Test error response."""
        response = ToolResponse(result={}, error="Something went wrong")
        assert not response.success
        assert response.error is not None

    def test_tool_response_string_representation(self):
        """Test response string representation."""
        response = ToolResponse(result={"key": "value"}, execution_ms=100)
        str_repr = str(response)
        assert "100ms" in str_repr or "100" in str_repr

        error_response = ToolResponse(result={}, error="Test error", execution_ms=50)
        error_str = str(error_response)
        assert "error" in error_str.lower()
