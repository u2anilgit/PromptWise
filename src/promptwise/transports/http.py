import time
from typing import Any

from .base import TransportAdapter
from promptwise.types import ToolRequest, ToolResponse


class HTTPAdapter(TransportAdapter):
    def __init__(self, provider: str, base_url: str, api_key: str = "", timeout_s: int = 30):
        super().__init__(f"http-{provider}")
        self.provider = provider.lower()
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_s = timeout_s

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        start = time.time()
        try:
            if self.provider == "codex":
                result = await self._call_codex(request)
            elif self.provider == "gemini":
                result = await self._call_gemini(request)
            else:
                return ToolResponse(result={}, error=f"Unknown provider: {self.provider}", execution_ms=int((time.time() - start) * 1000))
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result=result, error=None, execution_ms=ms)
        except ConnectionError as e:
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result={}, error=f"Connection: {e}", execution_ms=ms)
        except TimeoutError as e:
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result={}, error=f"Timeout: {e}", execution_ms=ms)
        except Exception as e:
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result={}, error=f"HTTP error: {type(e).__name__}: {e}", execution_ms=ms)

    async def _call_codex(self, request: ToolRequest) -> dict:
        tool, params = request.tool_name, request.params
        if tool == "route_request":
            text = params.get("text", "")
            if "refactor" in text.lower() or "architecture" in text.lower():
                model = "codex-5.5-max"
            elif "debug" in text.lower() or "test" in text.lower():
                model = "codex-5.5-pro"
            else:
                model = "codex-5.5-base"
            return {"recommended_model": model, "reason": f"Codex 5.5 selected", "alternatives": ["codex-5.5-base", "codex-5.5-pro"]}
        if tool == "compare_providers":
            return {"comparison": [{"provider": "codex", "model": "codex-5.5-pro", "total_cost_usd": 0.012},
                                   {"provider": "claude", "model": "claude-haiku-4-5", "total_cost_usd": 0.008}]}
        if tool == "rewrite_prompt":
            return {"original_text": params.get("text", ""), "rewritten_text": f"As a code expert, {params.get('text', '')}", "tokens_saved": 0}
        return {"status": "tool_not_supported_on_codex", "tool_name": tool}

    async def _call_gemini(self, request: ToolRequest) -> dict:
        return {"status": "supported", "tool_name": request.tool_name, "params_received": request.params}

    def start(self) -> None:
        if not self.api_key:
            print(f"Warning: {self.provider} API key not set")

    def stop(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True
