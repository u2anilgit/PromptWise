import time
from typing import Any

from .base import TransportAdapter
from promptwise.types import ToolRequest, ToolResponse


class MCPAdapter(TransportAdapter):
    def __init__(self):
        super().__init__("mcp")
        self.server_context = None
        self.call_tool_func = None

    def set_server(self, context: Any, call_tool_func: Any) -> None:
        self.server_context = context
        self.call_tool_func = call_tool_func

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        if not self.server_context or not self.call_tool_func:
            return ToolResponse(result={}, error="MCP adapter not initialized", execution_ms=0)

        self._set_session(request.session_id, request.context or {})
        start = time.time()
        try:
            result = await self.call_tool_func(self.server_context, request.tool_name, request.params)
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result=result if isinstance(result, dict) else {"output": str(result)}, error=None, execution_ms=ms)
        except ValueError as e:
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result={}, error=f"Tool not found: {e}", execution_ms=ms)
        except Exception as e:
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result={}, error=f"MCP error: {type(e).__name__}: {e}", execution_ms=ms)

    def _set_session(self, session_id: str, context: dict) -> None:
        if not self.server_context:
            return
        self.set_session_context(session_id, context)
        if hasattr(self.server_context, "session_id"):
            self.server_context.session_id = session_id

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    async def health_check(self) -> bool:
        if not self.server_context or not self.call_tool_func:
            return False
        try:
            resp = await self.call_tool(ToolRequest(tool_name="get_session_stats", params={}, session_id="health-check"))
            return resp.success
        except Exception:
            return False
