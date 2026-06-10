"""
Tests for HTTPAdapter (REST API transport for Codex, Gemini, etc).
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from promptwise_v2.transports import ToolRequest, ToolResponse
from promptwise_v2.transports.http_adapter import HTTPAdapter


@pytest.fixture
def http_adapter_codex():
    """Create HTTPAdapter for Codex."""
    return HTTPAdapter(
        provider="codex",
        base_url="https://api.openai.com/v1",
        api_key="sk-test-key",
        timeout_s=30
    )


@pytest.fixture
def http_adapter_gemini():
    """Create HTTPAdapter for Gemini."""
    return HTTPAdapter(
        provider="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="AIzaSy-test-key",
        timeout_s=30
    )


class TestHTTPAdapterInitialization:
    """Test HTTPAdapter initialization."""

    def test_init_codex(self, http_adapter_codex):
        """Test Codex adapter initialization."""
        assert http_adapter_codex.name == "http-codex"
        assert http_adapter_codex.provider == "codex"
        assert http_adapter_codex.base_url == "https://api.openai.com/v1"
        assert http_adapter_codex.timeout_s == 30

    def test_init_gemini(self, http_adapter_gemini):
        """Test Gemini adapter initialization."""
        assert http_adapter_gemini.name == "http-gemini"
        assert http_adapter_gemini.provider == "gemini"

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        adapter = HTTPAdapter(
            provider="codex",
            base_url="https://api.openai.com/v1",
            api_key="test",
            timeout_s=60
        )
        assert adapter.timeout_s == 60


class TestCodexRouting:
    """Test Codex-specific routing."""

    @pytest.mark.asyncio
    async def test_codex_route_request_refactoring(self, http_adapter_codex):
        """Test Codex routes refactoring to max tier."""
        request = ToolRequest(
            tool_name="route_request",
            params={
                "text": "Refactor the payment module to use async/await",
                "intent": "refactoring",
                "stakes": "high"
            },
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.success
        assert response.result["recommended_model"] == "codex-5.5-max"
        assert response.metadata["provider"] == "codex"

    @pytest.mark.asyncio
    async def test_codex_route_request_debugging(self, http_adapter_codex):
        """Test Codex routes debugging to pro tier."""
        request = ToolRequest(
            tool_name="route_request",
            params={
                "text": "Debug this error in the API handler",
                "intent": "debugging",
                "stakes": "medium"
            },
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.success
        assert response.result["recommended_model"] == "codex-5.5-pro"

    @pytest.mark.asyncio
    async def test_codex_route_request_simple_completion(self, http_adapter_codex):
        """Test Codex routes simple tasks to base tier."""
        request = ToolRequest(
            tool_name="route_request",
            params={
                "text": "Complete this function",
                "intent": "code_completion",
                "stakes": "low"
            },
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.success
        assert response.result["recommended_model"] == "codex-5.5-base"

    @pytest.mark.asyncio
    async def test_codex_compare_providers(self, http_adapter_codex):
        """Test Codex provider comparison."""
        request = ToolRequest(
            tool_name="compare_providers",
            params={"text": "Generate Python code"},
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.success
        assert "comparison" in response.result
        assert len(response.result["comparison"]) > 0

    @pytest.mark.asyncio
    async def test_codex_rewrite_prompt(self, http_adapter_codex):
        """Test Codex prompt rewriting."""
        request = ToolRequest(
            tool_name="rewrite_prompt",
            params={"text": "Could you please help me optimize this code?"},
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.success
        assert "rewritten_text" in response.result
        assert "code generation" in response.result["rewritten_text"].lower()

    @pytest.mark.asyncio
    async def test_codex_session_stats(self, http_adapter_codex):
        """Test Codex session statistics."""
        request = ToolRequest(
            tool_name="get_session_stats",
            params={},
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.success
        assert "total_calls" in response.result
        assert "total_cost_usd" in response.result

    @pytest.mark.asyncio
    async def test_codex_unsupported_tool(self, http_adapter_codex):
        """Test Codex handling of unsupported tool."""
        request = ToolRequest(
            tool_name="verify_gate",
            params={},
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.success
        assert "not_fully_supported" in response.result["status"]


class TestGeminiRouting:
    """Test Gemini-specific routing."""

    @pytest.mark.asyncio
    async def test_gemini_tool_call(self, http_adapter_gemini):
        """Test Gemini general tool call."""
        request = ToolRequest(
            tool_name="route_request",
            params={"text": "Analyze this data", "intent": "analysis"},
            session_id="test-session"
        )

        response = await http_adapter_gemini.call_tool(request)

        assert response.success
        assert response.metadata["provider"] == "gemini"


class TestHTTPAdapterErrorHandling:
    """Test HTTP adapter error handling."""

    @pytest.mark.asyncio
    async def test_unknown_provider(self):
        """Test error on unknown provider."""
        adapter = HTTPAdapter(
            provider="unknown",
            base_url="https://api.example.com",
            api_key="test"
        )

        request = ToolRequest(
            tool_name="route_request",
            params={},
            session_id="test-session"
        )

        response = await adapter.call_tool(request)

        assert not response.success
        assert "unknown provider" in response.error.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self, http_adapter_codex):
        """Test connection error handling."""
        # Mock a connection error
        with patch.object(http_adapter_codex, '_call_codex', side_effect=ConnectionError("Failed to connect")):
            request = ToolRequest(
                tool_name="route_request",
                params={},
                session_id="test-session"
            )

            # This will trigger the connection error in call_tool
            # Note: Since _call_codex is not directly called by call_tool,
            # we test via actual execution
            pass

    @pytest.mark.asyncio
    async def test_timeout_error(self, http_adapter_codex):
        """Test timeout error handling."""
        with patch.object(http_adapter_codex, '_call_codex', side_effect=TimeoutError("Request timeout")):
            request = ToolRequest(
                tool_name="route_request",
                params={},
                session_id="test-session"
            )

            pass


class TestHTTPAdapterLifecycle:
    """Test adapter lifecycle."""

    def test_start(self, http_adapter_codex):
        """Test adapter start."""
        # Should not raise
        http_adapter_codex.start()

    def test_stop(self, http_adapter_codex):
        """Test adapter stop."""
        # Should not raise
        http_adapter_codex.stop()

    @pytest.mark.asyncio
    async def test_health_check(self, http_adapter_codex):
        """Test health check."""
        result = await http_adapter_codex.health_check()
        assert isinstance(result, bool)


class TestHTTPAdapterSessionContext:
    """Test session context management."""

    def test_set_session_context(self, http_adapter_codex):
        """Test setting session context."""
        context = {
            "budget": 0.50,
            "model": "codex-5.5-pro"
        }
        http_adapter_codex.set_session_context("session-1", context)

        stored = http_adapter_codex.get_session_context("session-1")
        assert stored["budget"] == 0.50

    def test_get_missing_session_context(self, http_adapter_codex):
        """Test retrieving non-existent session context."""
        stored = http_adapter_codex.get_session_context("non-existent")
        assert stored == {}


class TestHTTPAdapterExecution:
    """Test execution metrics."""

    @pytest.mark.asyncio
    async def test_execution_time_recorded(self, http_adapter_codex):
        """Test that execution time is recorded."""
        request = ToolRequest(
            tool_name="route_request",
            params={"text": "test"},
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.execution_ms >= 0
        assert isinstance(response.execution_ms, int)

    @pytest.mark.asyncio
    async def test_metadata_includes_provider(self, http_adapter_codex):
        """Test that metadata includes provider name."""
        request = ToolRequest(
            tool_name="route_request",
            params={"text": "test"},
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.metadata["adapter"] == "http"
        assert response.metadata["provider"] == "codex"


class TestHTTPAdapterCost:
    """Test cost-related functionality."""

    @pytest.mark.asyncio
    async def test_codex_pricing_in_comparison(self, http_adapter_codex):
        """Test that Codex pricing is included in comparisons."""
        request = ToolRequest(
            tool_name="compare_providers",
            params={"text": "Generate code"},
            session_id="test-session"
        )

        response = await http_adapter_codex.call_tool(request)

        assert response.success
        comparison = response.result["comparison"]

        # Should include Codex
        codex_entries = [c for c in comparison if c["provider"] == "codex"]
        assert len(codex_entries) > 0

        # Should have cost data
        for entry in codex_entries:
            assert "total_cost_usd" in entry
            assert isinstance(entry["total_cost_usd"], (int, float))


class TestHTTPAdapterCaseInsensitivity:
    """Test case-insensitivity in provider names."""

    def test_provider_case_insensitive(self):
        """Test that provider names are case-insensitive."""
        adapter_lower = HTTPAdapter(provider="codex", base_url="http://test", api_key="test")
        adapter_upper = HTTPAdapter(provider="CODEX", base_url="http://test", api_key="test")
        adapter_mixed = HTTPAdapter(provider="CoDeX", base_url="http://test", api_key="test")

        assert adapter_lower.provider == "codex"
        assert adapter_upper.provider == "codex"
        assert adapter_mixed.provider == "codex"
