import asyncio
import json
import subprocess
import sys
import time
from typing import Any

from .base import TransportAdapter
from promptwise.types import ToolRequest, ToolResponse


class CLIAdapter(TransportAdapter):
    def __init__(self, endpoint: str, timeout_s: int = 30):
        super().__init__("cli")
        self.endpoint = endpoint
        self.timeout_s = timeout_s
        self.protocol, self.target = self._parse(endpoint)
        self.process: subprocess.Popen | None = None

    def _parse(self, endpoint: str) -> tuple[str, str]:
        if ":" not in endpoint:
            raise ValueError(f"Invalid endpoint: {endpoint}")
        proto, target = endpoint.split(":", 1)
        if proto not in ("stdio", "socket"):
            raise ValueError(f"Unknown protocol: {proto}")
        return proto, target

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        start = time.time()
        try:
            payload = json.dumps({"tool_name": request.tool_name, "params": request.params, "session_id": request.session_id, "context": request.context or {}})
            if self.protocol == "stdio":
                response = await self._send_stdio(payload)
            elif self.protocol == "socket":
                response = await self._send_socket(payload)
            else:
                raise ValueError(f"Unknown protocol: {self.protocol}")
            result = json.loads(response)
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result=result if isinstance(result, dict) else {"output": str(result)}, error=None, execution_ms=ms)
        except json.JSONDecodeError as e:
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result={}, error=f"Invalid JSON: {e}", execution_ms=ms)
        except TimeoutError:
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result={}, error=f"Timeout after {self.timeout_s}s", execution_ms=ms)
        except Exception as e:
            ms = int((time.time() - start) * 1000)
            return ToolResponse(result={}, error=f"CLI error: {type(e).__name__}: {e}", execution_ms=ms)

    async def _send_stdio(self, payload: str) -> str:
        if not self.process:
            self.process = subprocess.Popen(self.target, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
        process = self.process
        stdout, stderr = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, lambda: process.communicate(input=payload + "\n")),
            timeout=self.timeout_s,
        )
        if stderr:
            raise RuntimeError(f"CLI stderr: {stderr}")
        return stdout.strip()

    async def _send_socket(self, payload: str) -> str:
        if self.target.startswith("/"):
            if sys.platform == "win32":
                raise RuntimeError(
                    "Unix domain socket transport ('/path') is not supported on Windows; "
                    "use a TCP endpoint (host:port) instead."
                )
            reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(self.target), timeout=self.timeout_s)
        else:
            parts = self.target.split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid TCP: {self.target}")
            reader, writer = await asyncio.wait_for(asyncio.open_connection(parts[0], int(parts[1])), timeout=self.timeout_s)
        writer.write((payload + "\n").encode())
        await asyncio.wait_for(writer.drain(), timeout=self.timeout_s)
        data = await asyncio.wait_for(reader.readline(), timeout=self.timeout_s)
        writer.close()
        await writer.wait_closed()
        return data.decode().strip()

    def start(self) -> None:
        if self.protocol == "stdio":
            try:
                self.process = subprocess.Popen(self.target, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
            except Exception as e:
                print(f"Warning: Failed to start CLI '{self.target}': {e}")

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    async def health_check(self) -> bool:
        try:
            resp = await self.call_tool(ToolRequest(tool_name="ping", params={}, session_id="health-check"))
            return resp.success
        except Exception:
            return False
