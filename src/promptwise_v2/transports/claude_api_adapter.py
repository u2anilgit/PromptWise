"""
Claude API adapter for PromptWise.

Supports:
- Direct Claude API calls (claude.ai integration)
- Collaborative sessions via Claude API
- Token counting and cost estimation
"""

import asyncio
import json
import os
from typing import Dict, Any, Optional
import aiohttp

from . import TransportAdapter, ToolRequest, ToolResponse


class ClaudeAPIAdapter(TransportAdapter):
    """HTTP adapter for Anthropic Claude API."""

    def __init__(self, api_key: str = "", timeout_s: int = 30, model: str = "claude-opus-4-7"):
        super().__init__("claude-api")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.timeout_s = timeout_s
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"
        self.client: Optional[aiohttp.ClientSession] = None

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """Execute tool via Claude API."""
        try:
            result = await self._call_claude_tool(request)
            return ToolResponse(
                result=result,
                error=None,
                metadata={"platform": "claude-api", "model": self.model}
            )
        except Exception as e:
            return ToolResponse(
                result={},
                error=str(e),
                metadata={"platform": "claude-api"}
            )

    async def _call_claude_tool(self, request: ToolRequest) -> Dict[str, Any]:
        """Call PromptWise tool via Claude API."""
        if not self.client:
            self.client = aiohttp.ClientSession()

        headers = {
            "anthropic-version": "2023-06-01",
            "x-api-key": self.api_key,
            "content-type": "application/json"
        }

        tool_defs = self._get_promptwise_tools()
        tool_def = next((t for t in tool_defs if t["name"] == request.tool_name), None)

        if not tool_def:
            raise ValueError(f"Unknown tool: {request.tool_name}")

        prompt = self._build_prompt(request, tool_def)

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [tool_def],
        }

        async with self.client.post(
            f"{self.base_url}/messages",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout_s)
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"Claude API error: {data.get('error', {}).get('message', str(data))}")

            return self._extract_result(data, request.tool_name)

    def _build_prompt(self, request: ToolRequest, tool_def: Dict) -> str:
        """Build prompt for Claude to execute tool."""
        params_str = json.dumps(request.params, indent=2)
        return f"""Execute the {request.tool_name} tool with these parameters:

{params_str}

Tool description: {tool_def.get('description', '')}
Input schema: {json.dumps(tool_def.get('input_schema', {}))}

Return the result as valid JSON."""

    def _extract_result(self, response: Dict, tool_name: str) -> Dict[str, Any]:
        """Extract tool result from Claude response."""
        content = response.get("content", [])
        for block in content:
            if block.get("type") == "text":
                text = block.get("text", "")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw_response": text}
        return {"status": "completed"}

    def _get_promptwise_tools(self) -> list:
        """Get PromptWise tool definitions."""
        return [
            {
                "name": "route_request",
                "description": "Pick best Claude model by intent/stakes/budget",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "intent": {"type": "string", "enum": ["auto", "analysis", "coding", "writing", "general"]},
                        "stakes": {"type": "string", "enum": ["auto", "low", "medium", "high"]},
                        "monthly_budget_usd": {"type": "number"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "compress_prompt",
                "description": "Shrink prompt without losing meaning",
                "input_schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"]
                }
            },
            {
                "name": "owasp_scan",
                "description": "Scan code for security vulnerabilities",
                "input_schema": {
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"]
                }
            }
        ]

    async def health_check(self) -> bool:
        """Check API connectivity."""
        if not self.api_key:
            return False
        try:
            if not self.client:
                self.client = aiohttp.ClientSession()
            async with self.client.get(
                f"{self.base_url}/models",
                headers={"x-api-key": self.api_key},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    def stop(self):
        """Clean up resources."""
        if self.client:
            asyncio.get_event_loop().run_until_complete(self.client.close())
            self.client = None
