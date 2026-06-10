"""
Multi-platform transport abstraction layer.

PromptWise supports multiple deployment platforms (MCP, HTTP APIs, CLI tools).
This module provides a unified adapter pattern to route tool calls to any platform.

Supported transports:
  - MCP (Claude Code)
  - HTTP/REST (Codex 5.5, Gemini, custom APIs)
  - CLI/stdio (Antigravity, local tools)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class ToolRequest:
    """Unified request object for any platform."""

    tool_name: str
    params: Dict[str, Any]
    session_id: str
    context: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate request structure."""
        if not self.tool_name:
            raise ValueError("tool_name is required")
        if not self.session_id:
            raise ValueError("session_id is required")
        if not isinstance(self.params, dict):
            raise ValueError("params must be a dict")


@dataclass
class ToolResponse:
    """Unified response object from any platform."""

    result: Dict[str, Any]
    error: Optional[str] = None
    execution_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def success(self) -> bool:
        """Check if response indicates success."""
        return self.error is None

    def __str__(self) -> str:
        """Readable representation."""
        if self.error:
            return f"ToolResponse(error={self.error}, duration={self.execution_ms}ms)"
        return f"ToolResponse(result_keys={list(self.result.keys())}, duration={self.execution_ms}ms)"


class TransportAdapter(ABC):
    """
    Abstract base class for all platform transports.

    Each adapter handles:
    - Converting ToolRequest to platform-specific format
    - Making the actual call (API, RPC, stdio, etc.)
    - Converting response back to ToolResponse
    - Error handling and retry logic
    """

    def __init__(self, name: str = "unknown"):
        """Initialize adapter."""
        self.name = name
        self._session_contexts: Dict[str, Dict[str, Any]] = {}

    @abstractmethod
    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """
        Execute a tool call.

        Args:
            request: Unified ToolRequest (tool_name, params, session_id, context)

        Returns:
            ToolResponse with result or error

        Raises:
            ConnectionError: If unable to reach platform
            TimeoutError: If call exceeds timeout
            ValueError: If request is invalid
        """
        pass

    def set_session_context(self, session_id: str, context: Dict[str, Any]) -> None:
        """
        Set session-level configuration.

        Args:
            session_id: Unique session identifier
            context: {
                'budget': float (USD),
                'model': str (preferred model),
                'platform': str (platform name),
                'auto_role': bool (enable auto-role detection),
                'compression_level': str ('none', 'light', 'aggressive'),
                ...
            }
        """
        self._session_contexts[session_id] = context

    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Retrieve session context."""
        return self._session_contexts.get(session_id, {})

    def start(self) -> None:
        """
        Lifecycle hook: called when adapter starts.

        Subclasses can use this to:
        - Initialize connections
        - Verify API credentials
        - Load configuration
        """
        pass

    def stop(self) -> None:
        """
        Lifecycle hook: called when adapter stops.

        Subclasses can use this to:
        - Close connections
        - Clean up resources
        - Flush metrics
        """
        pass

    async def health_check(self) -> bool:
        """
        Check if adapter can reach its platform.

        Returns:
            True if healthy, False otherwise
        """
        return True


class BaseHTTPAdapter(TransportAdapter):
    """
    Base class for HTTP-based transports (REST APIs).

    Subclasses implement:
    - API endpoint configuration
    - Request serialization (endpoint + headers + body)
    - Response parsing
    - Provider-specific error handling
    """

    def __init__(self, name: str, base_url: str, api_key: str = "", timeout_s: int = 30):
        """Initialize HTTP adapter."""
        super().__init__(name)
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.client = None

    async def _make_request(self, method: str, endpoint: str, body: Dict) -> Dict:
        """
        Make HTTP request. Subclasses override for provider-specific logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            body: Request body

        Returns:
            Response dict
        """
        raise NotImplementedError("Subclass must implement _make_request")


class BaseCLIAdapter(TransportAdapter):
    """
    Base class for CLI/stdio-based transports.

    Subclasses implement:
    - Endpoint configuration (socket path, TCP address, etc.)
    - Request serialization (JSON, protobuf, etc.)
    - Response parsing
    - Process management (if spawning local process)
    """

    def __init__(self, name: str, endpoint: str, timeout_s: int = 30):
        """Initialize CLI adapter."""
        super().__init__(name)
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    async def _send_request(self, body: str) -> str:
        """
        Send request to endpoint and get response.

        Args:
            body: Serialized request (JSON string, etc.)

        Returns:
            Serialized response
        """
        raise NotImplementedError("Subclass must implement _send_request")


__all__ = [
    "ToolRequest",
    "ToolResponse",
    "TransportAdapter",
    "BaseHTTPAdapter",
    "BaseCLIAdapter",
]
