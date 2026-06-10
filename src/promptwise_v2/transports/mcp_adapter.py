"""
MCP (Model Context Protocol) adapter for Claude Code.

Wraps the existing MCP server as a TransportAdapter, enabling
PromptWise to be called via MCP protocol (existing behavior).
"""

import time
from typing import Dict, Any, Optional

from . import TransportAdapter, ToolRequest, ToolResponse


class MCPAdapter(TransportAdapter):
    """
    Adapter for MCP (Model Context Protocol) transport.

    Integrates with Claude Code's MCP server.
    This is the default transport for PromptWise v2.
    """

    def __init__(self):
        """Initialize MCP adapter."""
        super().__init__("mcp")
        self.server_context = None
        self.call_tool_func = None

    def set_server(self, context: Any, call_tool_func: Any) -> None:
        """
        Attach MCP server internals.

        This is called by the MCP server at startup to give the adapter
        access to the ServerContextV2 and call_tool_v2 function.

        Args:
            context: ServerContextV2 instance
            call_tool_func: call_tool_v2 async function
        """
        self.server_context = context
        self.call_tool_func = call_tool_func

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """
        Execute a tool call via MCP server.

        Args:
            request: ToolRequest (tool_name, params, session_id, context)

        Returns:
            ToolResponse with result or error
        """
        if not self.server_context or not self.call_tool_func:
            return ToolResponse(
                result={},
                error="MCP adapter not properly initialized (server_context or call_tool_func missing)",
                execution_ms=0
            )

        # Set session context on server
        self.set_session_context_on_server(request.session_id, request.context or {})

        # Execute tool
        start_time = time.time()
        try:
            result = await self.call_tool_func(
                self.server_context,
                request.tool_name,
                request.params
            )
            execution_ms = int((time.time() - start_time) * 1000)

            return ToolResponse(
                result=result if isinstance(result, dict) else {"output": str(result)},
                error=None,
                execution_ms=execution_ms,
                metadata={"adapter": "mcp", "server_version": getattr(self.server_context, "version", "unknown")}
            )

        except ValueError as e:
            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result={},
                error=f"Tool not found: {str(e)}",
                execution_ms=execution_ms,
                metadata={"adapter": "mcp", "error_type": "not_found"}
            )

        except Exception as e:
            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result={},
                error=f"MCP execution error: {type(e).__name__}: {str(e)}",
                execution_ms=execution_ms,
                metadata={"adapter": "mcp", "error_type": type(e).__name__}
            )

    def set_session_context_on_server(self, session_id: str, context: Dict[str, Any]) -> None:
        """
        Apply session context to MCP server state.

        Args:
            session_id: Session ID
            context: Session context dict
        """
        if not self.server_context:
            return

        # Store session context in our adapter
        self.set_session_context(session_id, context)

        # Apply to server context if available
        if hasattr(self.server_context, "session_id"):
            self.server_context.session_id = session_id
        if hasattr(self.server_context, "session_budget") and "budget" in context:
            self.server_context.session_budget = context["budget"]
        if hasattr(self.server_context, "preferred_model") and "model" in context:
            self.server_context.preferred_model = context["model"]

    def start(self) -> None:
        """Start MCP adapter."""
        # MCP server handles its own startup
        pass

    def stop(self) -> None:
        """Stop MCP adapter."""
        # MCP server handles its own shutdown
        pass

    async def health_check(self) -> bool:
        """Check if MCP server is healthy."""
        if not self.server_context or not self.call_tool_func:
            return False

        # Try a simple call to get_session_stats
        try:
            request = ToolRequest(
                tool_name="get_session_stats",
                params={},
                session_id="health-check"
            )
            response = await self.call_tool(request)
            return response.success
        except Exception:
            return False


__all__ = ["MCPAdapter"]
