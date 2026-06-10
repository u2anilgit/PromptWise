"""
Tests for adapter factory pattern.
"""

import pytest
import os
from unittest.mock import patch

from promptwise_v2.adapters import (
    create_adapter,
    get_default_platform,
    create_default_adapter
)
from promptwise_v2.transports.mcp_adapter import MCPAdapter
from promptwise_v2.transports.http_adapter import HTTPAdapter
from promptwise_v2.transports.cli_adapter import CLIAdapter


class TestAdapterFactory:
    """Test adapter factory function."""

    def test_create_mcp_adapter(self):
        """Test creating MCP adapter."""
        adapter = create_adapter("mcp")
        assert isinstance(adapter, MCPAdapter)
        assert adapter.name == "mcp"

    def test_create_mcp_adapter_case_insensitive(self):
        """Test case-insensitive platform name."""
        adapter_lower = create_adapter("mcp")
        adapter_upper = create_adapter("MCP")
        adapter_mixed = create_adapter("McP")

        assert isinstance(adapter_lower, MCPAdapter)
        assert isinstance(adapter_upper, MCPAdapter)
        assert isinstance(adapter_mixed, MCPAdapter)

    def test_create_codex_adapter_with_api_key(self):
        """Test creating Codex adapter with API key."""
        adapter = create_adapter("codex", {"codex_api_key": "sk-test-key"})
        assert isinstance(adapter, HTTPAdapter)
        assert adapter.provider == "codex"
        assert adapter.api_key == "sk-test-key"

    def test_create_codex_adapter_missing_api_key(self):
        """Test error when Codex API key missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="Codex API key required"):
                create_adapter("codex", {})

    def test_create_codex_adapter_from_env(self):
        """Test creating Codex adapter with env var."""
        with patch.dict(os.environ, {"CODEX_API_KEY": "sk-env-key"}):
            adapter = create_adapter("codex", {})
            assert isinstance(adapter, HTTPAdapter)
            assert adapter.api_key == "sk-env-key"

    def test_create_gemini_adapter_with_api_key(self):
        """Test creating Gemini adapter with API key."""
        adapter = create_adapter("gemini", {"gemini_api_key": "AIzaSy-test"})
        assert isinstance(adapter, HTTPAdapter)
        assert adapter.provider == "gemini"

    def test_create_gemini_adapter_missing_api_key(self):
        """Test error when Gemini API key missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="Gemini API key required"):
                create_adapter("gemini", {})

    def test_create_gemini_adapter_from_env(self):
        """Test creating Gemini adapter with env var."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSy-env"}):
            adapter = create_adapter("gemini", {})
            assert isinstance(adapter, HTTPAdapter)
            assert adapter.api_key == "AIzaSy-env"

    def test_create_antigravity_adapter_with_endpoint(self):
        """Test creating Antigravity adapter with endpoint."""
        adapter = create_adapter("antigravity", {"antigravity_endpoint": "localhost:5000"})
        assert isinstance(adapter, CLIAdapter)
        assert "socket:localhost:5000" in adapter.endpoint

    def test_create_antigravity_adapter_missing_endpoint(self):
        """Test error when Antigravity endpoint missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="Antigravity endpoint required"):
                create_adapter("antigravity", {})

    def test_create_antigravity_adapter_from_env(self):
        """Test creating Antigravity adapter with env var."""
        with patch.dict(os.environ, {"ANTIGRAVITY_ENDPOINT": "socket:/tmp/ag.sock"}):
            adapter = create_adapter("antigravity", {})
            assert isinstance(adapter, CLIAdapter)

    def test_create_adapter_unknown_platform(self):
        """Test error on unknown platform."""
        with pytest.raises(ValueError, match="Unknown platform"):
            create_adapter("unknown", {})

    def test_create_adapter_with_timeout(self):
        """Test passing custom timeout."""
        adapter = create_adapter("codex", {"codex_api_key": "test", "timeout_s": 60})
        assert adapter.timeout_s == 60

    def test_create_adapter_default_timeout(self):
        """Test default timeout."""
        adapter = create_adapter("codex", {"codex_api_key": "test"})
        assert adapter.timeout_s == 30


class TestAdapterFactoryEndpointConversion:
    """Test endpoint format conversion."""

    def test_antigravity_unix_socket_conversion(self):
        """Test Unix socket path conversion."""
        adapter = create_adapter("antigravity", {"antigravity_endpoint": "/tmp/antigravity.sock"})
        assert "socket:/tmp/antigravity.sock" in adapter.endpoint

    def test_antigravity_tcp_endpoint_conversion(self):
        """Test TCP endpoint (host:port) conversion."""
        adapter = create_adapter("antigravity", {"antigravity_endpoint": "192.168.1.100:8000"})
        assert "socket:192.168.1.100:8000" in adapter.endpoint

    def test_antigravity_localhost_conversion(self):
        """Test localhost:port conversion."""
        adapter = create_adapter("antigravity", {"antigravity_endpoint": "localhost:5000"})
        assert "socket:localhost:5000" in adapter.endpoint

    def test_antigravity_port_only_conversion(self):
        """Test port-only conversion."""
        adapter = create_adapter("antigravity", {"antigravity_endpoint": "9000"})
        assert "socket:localhost:9000" in adapter.endpoint

    def test_antigravity_existing_protocol_preserved(self):
        """Test that existing protocol is preserved."""
        adapter = create_adapter("antigravity", {"antigravity_endpoint": "socket:/var/run/tool.sock"})
        assert "socket:/var/run/tool.sock" in adapter.endpoint


class TestDefaultPlatform:
    """Test default platform selection."""

    def test_get_default_platform_not_set(self):
        """Test default when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            platform = get_default_platform()
            assert platform == "mcp"

    def test_get_default_platform_from_env(self):
        """Test default from environment variable."""
        with patch.dict(os.environ, {"PROMPTWISE_PLATFORM": "codex"}):
            platform = get_default_platform()
            assert platform == "codex"

    def test_get_default_platform_case_insensitive(self):
        """Test platform name is case-insensitive."""
        with patch.dict(os.environ, {"PROMPTWISE_PLATFORM": "GEMINI"}):
            platform = get_default_platform()
            assert platform == "gemini"


class TestCreateDefaultAdapter:
    """Test default adapter creation."""

    def test_create_default_adapter_mcp(self):
        """Test creating default adapter (should be MCP)."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = create_default_adapter()
            assert isinstance(adapter, MCPAdapter)

    def test_create_default_adapter_from_env(self):
        """Test creating default adapter from environment."""
        with patch.dict(os.environ, {"PROMPTWISE_PLATFORM": "gemini", "GEMINI_API_KEY": "test"}):
            adapter = create_default_adapter()
            assert isinstance(adapter, HTTPAdapter)
            assert adapter.provider == "gemini"

    def test_create_default_adapter_error_on_missing_config(self):
        """Test error when required config missing for non-MCP platform."""
        with patch.dict(os.environ, {"PROMPTWISE_PLATFORM": "codex"}, clear=True):
            with pytest.raises(RuntimeError):
                create_default_adapter()


class TestAdapterConfiguration:
    """Test adapter configuration options."""

    def test_codex_adapter_url(self):
        """Test Codex adapter base URL."""
        adapter = create_adapter("codex", {"codex_api_key": "test"})
        assert adapter.base_url == "https://api.openai.com/v1"

    def test_gemini_adapter_url(self):
        """Test Gemini adapter base URL."""
        adapter = create_adapter("gemini", {"gemini_api_key": "test"})
        assert adapter.base_url == "https://generativelanguage.googleapis.com/v1beta/models"

    def test_mcp_adapter_has_no_url(self):
        """Test MCP adapter doesn't have base URL."""
        adapter = create_adapter("mcp")
        assert not hasattr(adapter, 'base_url') or adapter.base_url is None


class TestAdapterPlatformNames:
    """Test platform name variations."""

    def test_codex_variants(self):
        """Test Codex platform name variants."""
        for name in ["codex", "CODEX", "Codex", "CoDeX"]:
            adapter = create_adapter(name, {"codex_api_key": "test"})
            assert adapter.provider == "codex"

    def test_gemini_variants(self):
        """Test Gemini platform name variants."""
        for name in ["gemini", "GEMINI", "Gemini", "GeMinI"]:
            adapter = create_adapter(name, {"gemini_api_key": "test"})
            assert adapter.provider == "gemini"

    def test_antigravity_variants(self):
        """Test Antigravity platform name variants."""
        for name in ["antigravity", "ANTIGRAVITY", "Antigravity"]:
            adapter = create_adapter(name, {"antigravity_endpoint": "localhost:5000"})
            assert isinstance(adapter, CLIAdapter)

    def test_mcp_variants(self):
        """Test MCP platform name variants."""
        for name in ["mcp", "MCP", "Mcp", "McP"]:
            adapter = create_adapter(name)
            assert isinstance(adapter, MCPAdapter)


class TestAdapterAPIKeyPrecedence:
    """Test API key source precedence."""

    def test_config_takes_precedence_over_env(self):
        """Test that config dict takes precedence over environment."""
        with patch.dict(os.environ, {"CODEX_API_KEY": "env-key"}):
            adapter = create_adapter("codex", {"codex_api_key": "config-key"})
            assert adapter.api_key == "config-key"

    def test_env_used_when_config_empty(self):
        """Test that environment is used when config is empty."""
        with patch.dict(os.environ, {"CODEX_API_KEY": "env-key"}):
            adapter = create_adapter("codex", {})
            assert adapter.api_key == "env-key"

    def test_none_in_config_uses_env(self):
        """Test that None in config falls back to env."""
        with patch.dict(os.environ, {"CODEX_API_KEY": "env-key"}):
            adapter = create_adapter("codex", {"codex_api_key": None})
            assert adapter.api_key == "env-key"
