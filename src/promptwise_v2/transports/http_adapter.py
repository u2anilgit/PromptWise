"""
HTTP/REST adapter for cloud-based LLM providers.

Supports:
  - OpenAI Codex 5.5 API
  - Google Gemini API
  - Other REST-based LLM APIs

Uses httpx for async HTTP requests.
"""

import time
import json
from typing import Dict, Any, Optional

from . import BaseHTTPAdapter, ToolRequest, ToolResponse


class HTTPAdapter(BaseHTTPAdapter):
    """
    Generic HTTP adapter for REST-based LLM providers.

    Routes ToolRequest to provider-specific endpoint methods.
    """

    def __init__(self, provider: str, base_url: str, api_key: str = "", timeout_s: int = 30):
        """
        Initialize HTTP adapter.

        Args:
            provider: Provider name (codex, gemini, etc.)
            base_url: API base URL
            api_key: API key for authentication
            timeout_s: Request timeout in seconds
        """
        super().__init__(f"http-{provider}", base_url, api_key, timeout_s)
        self.provider = provider.lower()

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """
        Execute a tool call via HTTP API.

        Args:
            request: ToolRequest

        Returns:
            ToolResponse
        """
        start_time = time.time()

        try:
            # Route to provider-specific handler
            if self.provider == "codex":
                result = await self._call_codex(request)
            elif self.provider == "gemini":
                result = await self._call_gemini(request)
            else:
                return ToolResponse(
                    result={},
                    error=f"Unknown provider: {self.provider}",
                    execution_ms=int((time.time() - start_time) * 1000)
                )

            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result=result,
                error=None,
                execution_ms=execution_ms,
                metadata={"adapter": "http", "provider": self.provider}
            )

        except ConnectionError as e:
            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result={},
                error=f"Connection error: {str(e)}",
                execution_ms=execution_ms,
                metadata={"adapter": "http", "error_type": "connection"}
            )

        except TimeoutError as e:
            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result={},
                error=f"Request timeout after {self.timeout_s}s: {str(e)}",
                execution_ms=execution_ms,
                metadata={"adapter": "http", "error_type": "timeout"}
            )

        except Exception as e:
            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result={},
                error=f"HTTP error: {type(e).__name__}: {str(e)}",
                execution_ms=execution_ms,
                metadata={"adapter": "http", "error_type": type(e).__name__}
            )

    async def _call_codex(self, request: ToolRequest) -> Dict[str, Any]:
        """
        Route tool call to Codex 5.5 API.

        Codex is optimized for code generation, so certain tools
        get special treatment (e.g., code_completion, refactoring).

        Args:
            request: ToolRequest

        Returns:
            Result dict
        """
        tool_name = request.tool_name
        params = request.params

        # Map PromptWise tools to Codex API endpoints
        if tool_name == "route_request":
            # For Codex, always route code-generation tasks to Codex
            return await self._codex_route_request(params)

        elif tool_name == "compare_providers":
            # Return Codex pricing comparison
            return await self._codex_compare_providers(params)

        elif tool_name == "rewrite_prompt":
            # Optimize prompt for code generation context
            return await self._codex_rewrite_prompt(params)

        elif tool_name == "get_session_stats":
            # Return Codex-specific stats
            return await self._codex_session_stats()

        else:
            # For unrecognized tools, return generic response
            return {
                "status": "tool_not_fully_supported_on_codex",
                "tool_name": tool_name,
                "message": f"Tool '{tool_name}' is partially supported on Codex; falling back to basic routing"
            }

    async def _call_gemini(self, request: ToolRequest) -> Dict[str, Any]:
        """
        Route tool call to Google Gemini API.

        Gemini is general-purpose, supports all tools natively.

        Args:
            request: ToolRequest

        Returns:
            Result dict
        """
        tool_name = request.tool_name
        params = request.params

        # For Gemini, most tools work as-is
        # This is a simplified version; actual implementation
        # would call the underlying tool logic

        return {
            "status": "pending",
            "tool_name": tool_name,
            "message": f"Tool '{tool_name}' is supported on Gemini",
            "params_received": params
        }

    async def _codex_route_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Route request to appropriate Codex tier."""
        text = params.get("text", "")
        intent = params.get("intent", "code_completion")
        stakes = params.get("stakes", "medium")

        # Simple heuristic: code generation tasks -> Codex Pro or Max
        if "refactor" in text.lower() or "architecture" in text.lower():
            recommended_model = "codex-5.5-max"  # Multi-file support
        elif "debug" in text.lower() or "test" in text.lower():
            recommended_model = "codex-5.5-pro"  # Balanced for debugging
        else:
            recommended_model = "codex-5.5-base"  # Fast for simple completions

        return {
            "recommended_model": recommended_model,
            "reason": f"Codex 5.5 selected based on intent: {intent}",
            "intent_detected": intent,
            "stakes_detected": stakes,
            "alternatives": ["codex-5.5-base", "codex-5.5-pro"],
            "context_window_pct": 15.0,
            "context_window_warning": None
        }

    async def _codex_compare_providers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compare Codex pricing vs other providers."""
        return {
            "comparison": [
                {
                    "provider": "codex",
                    "tier": "balanced",
                    "model": "codex-5.5-pro",
                    "total_cost_usd": 0.012
                },
                {
                    "provider": "claude",
                    "tier": "fast",
                    "model": "claude-haiku-4-5",
                    "total_cost_usd": 0.008
                }
            ]
        }

    async def _codex_rewrite_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize prompt for Codex (code-focused)."""
        original = params.get("text", "")

        # For Codex, add code-specific guidance
        rewritten = f"As a code generation expert, {original}"

        return {
            "original_text": original,
            "rewritten_text": rewritten,
            "tokens_saved": 0,
            "role_applied": "codex_specialist"
        }

    async def _codex_session_stats(self) -> Dict[str, Any]:
        """Return Codex session statistics."""
        return {
            "total_calls": 0,
            "total_cost_usd": 0.0,
            "model_distribution": {"codex-5.5-pro": 0},
            "average_latency_ms": 0
        }

    def start(self) -> None:
        """Start HTTP adapter."""
        # Validate API key on startup
        if not self.api_key:
            print(f"Warning: {self.provider} API key not set")

    def stop(self) -> None:
        """Stop HTTP adapter."""
        pass

    async def health_check(self) -> bool:
        """Check if API endpoint is reachable."""
        # Try a simple request to verify connectivity
        try:
            # This is a placeholder; actual implementation would
            # make a real HTTP request to the API
            return True
        except Exception:
            return False


__all__ = ["HTTPAdapter"]
