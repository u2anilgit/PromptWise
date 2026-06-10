"""
Claude Collaboration API adapter.

Supports multi-user sessions, team workspaces, and shared contexts.
Built on Claude API with team/workspace extensions.
"""

import json
import os
from typing import Dict, Any, Optional, List
import aiohttp

from . import TransportAdapter, ToolRequest, ToolResponse


class CollaborationAdapter(TransportAdapter):
    """HTTP adapter for Claude Collaboration API (team/workspace features)."""

    def __init__(self, api_key: str = "", team_id: str = "", workspace_id: str = "", timeout_s: int = 30):
        super().__init__("claude-collaboration")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.team_id = team_id or os.getenv("ANTHROPIC_TEAM_ID", "")
        self.workspace_id = workspace_id or os.getenv("ANTHROPIC_WORKSPACE_ID", "")
        self.timeout_s = timeout_s
        self.base_url = "https://api.anthropic.com/v1"
        self.client: Optional[aiohttp.ClientSession] = None

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """Execute tool in collaboration context."""
        try:
            result = await self._call_with_collaboration(request)
            return ToolResponse(
                result=result,
                error=None,
                metadata={
                    "platform": "claude-collaboration",
                    "team_id": self.team_id,
                    "workspace_id": self.workspace_id
                }
            )
        except Exception as e:
            return ToolResponse(
                result={},
                error=str(e),
                metadata={"platform": "claude-collaboration"}
            )

    async def _call_with_collaboration(self, request: ToolRequest) -> Dict[str, Any]:
        """Execute tool with team/workspace context."""
        if not self.client:
            self.client = aiohttp.ClientSession()

        headers = self._build_headers()

        payload = {
            "tool_name": request.tool_name,
            "params": request.params,
            "session_id": request.session_id,
            "context": request.context or {},
            "collaboration": {
                "team_id": self.team_id,
                "workspace_id": self.workspace_id,
                "shared": True
            }
        }

        async with self.client.post(
            f"{self.base_url}/tools/execute",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout_s)
        ) as resp:
            data = await resp.json()
            if resp.status >= 400:
                raise RuntimeError(f"Collaboration API error: {data.get('error', {}).get('message', str(data))}")
            return data.get("result", {})

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with auth and team context."""
        headers = {
            "anthropic-version": "2023-06-01",
            "x-api-key": self.api_key,
            "content-type": "application/json"
        }
        if self.team_id:
            headers["x-team-id"] = self.team_id
        if self.workspace_id:
            headers["x-workspace-id"] = self.workspace_id
        return headers

    def set_team_context(self, team_id: str, workspace_id: str) -> None:
        """Update team/workspace context."""
        self.team_id = team_id
        self.workspace_id = workspace_id

    async def get_team_members(self) -> List[Dict[str, Any]]:
        """Get active team members in workspace."""
        if not self.client:
            self.client = aiohttp.ClientSession()

        async with self.client.get(
            f"{self.base_url}/teams/{self.team_id}/members",
            headers=self._build_headers(),
            timeout=aiohttp.ClientTimeout(total=self.timeout_s)
        ) as resp:
            data = await resp.json()
            return data.get("members", [])

    async def share_session(self, session_id: str, user_emails: List[str]) -> Dict[str, Any]:
        """Share a session with team members."""
        if not self.client:
            self.client = aiohttp.ClientSession()

        payload = {"session_id": session_id, "users": user_emails}

        async with self.client.post(
            f"{self.base_url}/sessions/share",
            json=payload,
            headers=self._build_headers(),
            timeout=aiohttp.ClientTimeout(total=self.timeout_s)
        ) as resp:
            return await resp.json()

    async def get_shared_context(self, session_id: str) -> Dict[str, Any]:
        """Get shared context from team session."""
        if not self.client:
            self.client = aiohttp.ClientSession()

        async with self.client.get(
            f"{self.base_url}/sessions/{session_id}/context",
            headers=self._build_headers(),
            timeout=aiohttp.ClientTimeout(total=self.timeout_s)
        ) as resp:
            return await resp.json()

    async def health_check(self) -> bool:
        """Check collaboration API connectivity."""
        if not self.api_key or not self.team_id:
            return False
        try:
            if not self.client:
                self.client = aiohttp.ClientSession()
            async with self.client.get(
                f"{self.base_url}/teams/{self.team_id}",
                headers=self._build_headers(),
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    def stop(self):
        """Clean up resources."""
        if self.client:
            import asyncio
            asyncio.get_event_loop().run_until_complete(self.client.close())
            self.client = None
