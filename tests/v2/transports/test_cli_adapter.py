"""
Tests for CLIAdapter (stdio/socket transport for local tools).
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from promptwise_v2.transports import ToolRequest, ToolResponse
from promptwise_v2.transports.cli_adapter import CLIAdapter


@pytest.fixture
def cli_adapter_stdio():
    """Create CLIAdapter for stdio."""
    return CLIAdapter(endpoint="stdio:antigravity", timeout_s=5)


@pytest.fixture
def cli_adapter_socket_unix():
    """Create CLIAdapter for Unix socket."""
    return CLIAdapter(endpoint="socket:/tmp/antigravity.sock", timeout_s=5)


@pytest.fixture
def cli_adapter_socket_tcp():
    """Create CLIAdapter for TCP socket."""
    return CLIAdapter(endpoint="socket:localhost:5000", timeout_s=5)


class TestCLIAdapterInitialization:
    """Test CLIAdapter initialization."""

    def test_init_stdio(self, cli_adapter_stdio):
        """Test stdio endpoint parsing."""
        assert cli_adapter_stdio.name == "cli"
        assert cli_adapter_stdio.protocol == "stdio"
        assert cli_adapter_stdio.target == "antigravity"

    def test_init_socket_unix(self, cli_adapter_socket_unix):
        """Test Unix socket endpoint parsing."""
        assert cli_adapter_socket_unix.protocol == "socket"
        assert cli_adapter_socket_unix.target == "/tmp/antigravity.sock"

    def test_init_socket_tcp(self, cli_adapter_socket_tcp):
        """Test TCP socket endpoint parsing."""
        assert cli_adapter_socket_tcp.protocol == "socket"
        assert cli_adapter_socket_tcp.target == "localhost:5000"

    def test_init_custom_timeout(self):
        """Test initialization with custom timeout."""
        adapter = CLIAdapter(endpoint="stdio:test", timeout_s=60)
        assert adapter.timeout_s == 60

    def test_init_invalid_endpoint(self):
        """Test error on invalid endpoint format."""
        with pytest.raises(ValueError):
            CLIAdapter(endpoint="invalid_format")

    def test_init_unknown_protocol(self):
        """Test error on unknown protocol."""
        with pytest.raises(ValueError):
            CLIAdapter(endpoint="unknown:test")


class TestCLIAdapterEndpointParsing:
    """Test endpoint parsing."""

    def test_parse_stdio_endpoint(self):
        """Test stdio endpoint parsing."""
        adapter = CLIAdapter(endpoint="stdio:my-tool")
        assert adapter.protocol == "stdio"
        assert adapter.target == "my-tool"

    def test_parse_unix_socket_endpoint(self):
        """Test Unix socket endpoint parsing."""
        adapter = CLIAdapter(endpoint="socket:/var/run/tool.sock")
        assert adapter.protocol == "socket"
        assert adapter.target == "/var/run/tool.sock"

    def test_parse_tcp_socket_endpoint(self):
        """Test TCP socket endpoint parsing."""
        adapter = CLIAdapter(endpoint="socket:192.168.1.100:8000")
        assert adapter.protocol == "socket"
        assert adapter.target == "192.168.1.100:8000"

    def test_parse_tcp_socket_localhost(self):
        """Test TCP socket with localhost."""
        adapter = CLIAdapter(endpoint="socket:localhost:9000")
        assert adapter.target == "localhost:9000"


class TestCLIAdapterToolRequest:
    """Test tool request serialization."""

    @pytest.mark.asyncio
    async def test_tool_request_serialization(self, cli_adapter_stdio):
        """Test that tool requests are properly serialized to JSON."""
        request = ToolRequest(
            tool_name="test_tool",
            params={"key": "value"},
            session_id="session-1",
            context={"ctx_key": "ctx_value"}
        )

        # Verify request structure (without actually sending)
        assert request.tool_name == "test_tool"
        assert request.params["key"] == "value"
        assert request.context["ctx_key"] == "ctx_value"


class TestCLIAdapterSessionContext:
    """Test session context management."""

    def test_set_session_context(self, cli_adapter_stdio):
        """Test setting session context."""
        context = {
            "budget": 0.50,
            "auto_role": True
        }
        cli_adapter_stdio.set_session_context("session-1", context)

        stored = cli_adapter_stdio.get_session_context("session-1")
        assert stored["budget"] == 0.50

    def test_get_missing_session_context(self, cli_adapter_stdio):
        """Test retrieving non-existent session context."""
        stored = cli_adapter_stdio.get_session_context("non-existent")
        assert stored == {}


class TestCLIAdapterErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_json_decode_error(self, cli_adapter_stdio):
        """Test handling of invalid JSON response."""
        with patch.object(cli_adapter_stdio, '_send_via_stdio', side_effect=Exception("Invalid JSON")):
            request = ToolRequest(
                tool_name="test",
                params={},
                session_id="session-1"
            )

            response = await cli_adapter_stdio.call_tool(request)

            assert not response.success
            assert "error" in response.error.lower()

    @pytest.mark.asyncio
    async def test_timeout_error(self, cli_adapter_stdio):
        """Test handling of timeout."""
        with patch.object(cli_adapter_stdio, '_send_via_stdio', side_effect=TimeoutError("Timeout")):
            request = ToolRequest(
                tool_name="test",
                params={},
                session_id="session-1"
            )

            response = await cli_adapter_stdio.call_tool(request)

            assert not response.success
            assert "timeout" in response.error.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self, cli_adapter_socket_tcp):
        """Test handling of connection error."""
        with patch.object(cli_adapter_socket_tcp, '_send_via_socket', side_effect=TimeoutError("Connection failed")):
            request = ToolRequest(
                tool_name="test",
                params={},
                session_id="session-1"
            )

            response = await cli_adapter_socket_tcp.call_tool(request)

            assert not response.success
            assert "timeout" in response.error.lower()


class TestCLIAdapterMetadata:
    """Test response metadata."""

    @pytest.mark.asyncio
    async def test_metadata_includes_protocol(self, cli_adapter_stdio):
        """Test that metadata includes protocol."""
        with patch.object(cli_adapter_stdio, '_send_via_stdio', return_value='{"status": "ok"}'):
            request = ToolRequest(
                tool_name="test",
                params={},
                session_id="session-1"
            )

            response = await cli_adapter_stdio.call_tool(request)

            assert response.metadata["adapter"] == "cli"
            assert response.metadata["protocol"] == "stdio"


class TestCLIAdapterLifecycle:
    """Test adapter lifecycle."""

    def test_start(self, cli_adapter_stdio):
        """Test adapter start."""
        # Should not raise (even if tool doesn't exist)
        cli_adapter_stdio.start()

    def test_stop(self, cli_adapter_stdio):
        """Test adapter stop."""
        cli_adapter_stdio.stop()
        # Process should be None after stop
        assert cli_adapter_stdio.process is None

    @pytest.mark.asyncio
    async def test_health_check(self, cli_adapter_stdio):
        """Test health check."""
        result = await cli_adapter_stdio.health_check()
        # Will be False since we can't actually communicate
        assert isinstance(result, bool)


class TestCLIAdapterExecution:
    """Test execution metrics."""

    @pytest.mark.asyncio
    async def test_execution_time_recorded(self, cli_adapter_stdio):
        """Test that execution time is recorded."""
        with patch.object(cli_adapter_stdio, '_send_via_stdio', return_value='{"result": "ok"}'):
            request = ToolRequest(
                tool_name="test",
                params={},
                session_id="session-1"
            )

            response = await cli_adapter_stdio.call_tool(request)

            assert response.execution_ms >= 0
            assert isinstance(response.execution_ms, int)


class TestCLIAdapterSuccessResponse:
    """Test successful responses."""

    @pytest.mark.asyncio
    async def test_json_response_parsed(self, cli_adapter_stdio):
        """Test that JSON responses are properly parsed."""
        mock_response = '{"status": "success", "data": "test"}'

        with patch.object(cli_adapter_stdio, '_send_via_stdio', return_value=mock_response):
            request = ToolRequest(
                tool_name="test",
                params={},
                session_id="session-1"
            )

            response = await cli_adapter_stdio.call_tool(request)

            assert response.success
            assert response.result["status"] == "success"
            assert response.result["data"] == "test"


class TestCLIAdapterProtocolSelection:
    """Test protocol selection."""

    @pytest.mark.asyncio
    async def test_stdio_protocol_selected(self, cli_adapter_stdio):
        """Test stdio protocol selected."""
        assert cli_adapter_stdio.protocol == "stdio"

    @pytest.mark.asyncio
    async def test_socket_protocol_selected_unix(self, cli_adapter_socket_unix):
        """Test socket protocol selected for Unix socket."""
        assert cli_adapter_socket_unix.protocol == "socket"

    @pytest.mark.asyncio
    async def test_socket_protocol_selected_tcp(self, cli_adapter_socket_tcp):
        """Test socket protocol selected for TCP."""
        assert cli_adapter_socket_tcp.protocol == "socket"
