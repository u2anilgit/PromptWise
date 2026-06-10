"""
CLI/stdio adapter for local command-line tools.

Supports communication with local tools via:
  - stdio (JSON in/out)
  - Unix sockets
  - TCP sockets

Examples:
  - Antigravity CLI
  - Local development servers
"""

import time
import json
import asyncio
import subprocess
from typing import Dict, Any, Optional

from . import BaseCLIAdapter, ToolRequest, ToolResponse


class CLIAdapter(BaseCLIAdapter):
    """
    Adapter for CLI/stdio-based local tools.

    Communicates via JSON over stdin/stdout or socket.
    """

    def __init__(self, endpoint: str, timeout_s: int = 30):
        """
        Initialize CLI adapter.

        Args:
            endpoint: Tool endpoint
              - Format: "stdio:CMD_NAME" for subprocess
              - Format: "socket:path/to/socket" for Unix socket
              - Format: "socket:host:port" for TCP socket
            timeout_s: Request timeout in seconds
        """
        super().__init__("cli", endpoint, timeout_s)
        self.protocol, self.target = self._parse_endpoint(endpoint)
        self.process: Optional[subprocess.Popen] = None

    def _parse_endpoint(self, endpoint: str) -> tuple:
        """
        Parse endpoint string.

        Args:
            endpoint: Endpoint specification

        Returns:
            (protocol, target) tuple
        """
        if ":" not in endpoint:
            raise ValueError(f"Invalid endpoint format: {endpoint}")

        protocol, target = endpoint.split(":", 1)

        if protocol not in ["stdio", "socket"]:
            raise ValueError(f"Unknown protocol: {protocol}")

        return protocol, target

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """
        Execute a tool call via CLI.

        Args:
            request: ToolRequest

        Returns:
            ToolResponse
        """
        start_time = time.time()

        try:
            # Serialize request to JSON
            request_json = {
                "tool_name": request.tool_name,
                "params": request.params,
                "session_id": request.session_id,
                "context": request.context or {}
            }
            request_str = json.dumps(request_json)

            # Send request and get response
            if self.protocol == "stdio":
                response_str = await self._send_via_stdio(request_str)
            elif self.protocol == "socket":
                response_str = await self._send_via_socket(request_str)
            else:
                raise ValueError(f"Unknown protocol: {self.protocol}")

            # Parse response
            result = json.loads(response_str)

            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result=result if isinstance(result, dict) else {"output": str(result)},
                error=None,
                execution_ms=execution_ms,
                metadata={"adapter": "cli", "protocol": self.protocol}
            )

        except json.JSONDecodeError as e:
            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result={},
                error=f"Invalid JSON response: {str(e)}",
                execution_ms=execution_ms,
                metadata={"adapter": "cli", "error_type": "json_decode"}
            )

        except TimeoutError:
            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result={},
                error=f"CLI call timeout after {self.timeout_s}s",
                execution_ms=execution_ms,
                metadata={"adapter": "cli", "error_type": "timeout"}
            )

        except Exception as e:
            execution_ms = int((time.time() - start_time) * 1000)
            return ToolResponse(
                result={},
                error=f"CLI error: {type(e).__name__}: {str(e)}",
                execution_ms=execution_ms,
                metadata={"adapter": "cli", "error_type": type(e).__name__}
            )

    async def _send_via_stdio(self, request_str: str) -> str:
        """
        Send request via subprocess stdin/stdout.

        Args:
            request_str: JSON request string

        Returns:
            JSON response string
        """
        try:
            # Spawn subprocess if not already running
            if not self.process:
                self.process = subprocess.Popen(
                    self.target,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    text=True
                )

            # Send request
            stdout, stderr = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.process.communicate(input=request_str + "\n")
                ),
                timeout=self.timeout_s
            )

            if stderr:
                raise RuntimeError(f"CLI error: {stderr}")

            return stdout.strip()

        except subprocess.TimeoutExpired:
            if self.process:
                self.process.kill()
                self.process = None
            raise TimeoutError("CLI subprocess timeout")

    async def _send_via_socket(self, request_str: str) -> str:
        """
        Send request via Unix or TCP socket.

        Args:
            request_str: JSON request string

        Returns:
            JSON response string
        """
        try:
            # Determine socket type (Unix or TCP)
            if self.target.startswith("/"):
                # Unix socket
                reader, writer = await asyncio.wait_for(
                    asyncio.open_unix_connection(self.target),
                    timeout=self.timeout_s
                )
            else:
                # TCP socket (host:port)
                parts = self.target.split(":")
                if len(parts) != 2:
                    raise ValueError(f"Invalid TCP endpoint: {self.target}")
                host, port = parts
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, int(port)),
                    timeout=self.timeout_s
                )

            # Send request
            writer.write((request_str + "\n").encode())
            await asyncio.wait_for(writer.drain(), timeout=self.timeout_s)

            # Read response
            response_data = await asyncio.wait_for(
                reader.readline(),
                timeout=self.timeout_s
            )

            writer.close()
            await writer.wait_closed()

            return response_data.decode().strip()

        except (OSError, asyncio.TimeoutError) as e:
            raise TimeoutError(f"Socket operation timeout: {str(e)}")

    def start(self) -> None:
        """Start CLI adapter."""
        if self.protocol == "stdio":
            # Pre-spawn subprocess to verify tool exists
            try:
                self.process = subprocess.Popen(
                    self.target,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    text=True
                )
            except Exception as e:
                print(f"Warning: Failed to start CLI tool '{self.target}': {e}")

    def stop(self) -> None:
        """Stop CLI adapter."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    async def health_check(self) -> bool:
        """Check if CLI endpoint is reachable."""
        try:
            request = ToolRequest(
                tool_name="ping",
                params={},
                session_id="health-check"
            )
            response = await self.call_tool(request)
            return response.success
        except Exception:
            return False


__all__ = ["CLIAdapter"]
