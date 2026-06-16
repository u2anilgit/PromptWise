from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from promptwise.types import ToolRequest, ToolResponse


class TransportAdapter(ABC):
    def __init__(self, name: str = "unknown"):
        self.name = name
        self._session_contexts: dict[str, dict] = {}

    @abstractmethod
    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        pass

    def set_session_context(self, session_id: str, context: dict) -> None:
        self._session_contexts[session_id] = context

    def get_session_context(self, session_id: str) -> dict:
        return self._session_contexts.get(session_id, {})

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True


__all__ = ["TransportAdapter", "ToolRequest", "ToolResponse"]
