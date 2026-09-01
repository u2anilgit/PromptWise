"""transports.http_server -- optional Streamable HTTP MCP transport.

Alongside (never replacing) server.py's stdio entrypoint. Selected via
PROMPTWISE_TRANSPORT=http (default stdio, zero behavior change for
existing users). Auth is fail-closed: a missing or invalid Bearer token
never reaches the MCP session manager -- see
docs/superpowers/specs/2026-09-01-remote-mcp-transport-design.md.

Session identity: each incoming connection gets its own PromptWise
session_id (see core/session_context.py) derived from the authenticated
credential_id, set on the contextvars.ContextVar for that connection's
async context before any tool call executes on it, and reset afterward.
This makes concurrent connections from different tokens never share a
session_id, and makes the same token's reconnects stable (useful for
per-developer cost rollups), unlike a fresh random id per HTTP request.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from promptwise.dashboard.auth import find_identity, load_credentials
from promptwise.core.session_context import set_current_session_id, reset_current_session_id


def _extract_bearer_token(headers: list[tuple[bytes, bytes]]) -> str | None:
    """Raw ASGI header list -> the Bearer token, or None. Reads scope
    headers directly rather than via a Starlette Request wrapper, since
    wrapping would consume the request body the session manager still
    needs to read itself."""
    for name, value in headers:
        if name.lower() == b"authorization":
            text = value.decode("latin-1")
            if text.startswith("Bearer "):
                return text[len("Bearer "):]
    return None


def build_app(ctx: Any, credentials_path: str = "config/mcp_auth.yaml") -> Starlette:
    """Build the Starlette app. `ctx` is the ServerContext the existing
    call_tool(ctx, name, arguments) dispatch already uses -- shared
    across all connections (memory/router/etc. are process-wide
    services; only session_id and remote_identity are per-connection)."""
    from mcp.server import Server
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from mcp.types import Tool, TextContent
    from promptwise.server import list_tools, call_tool

    mcp_server = Server("promptwise")

    @mcp_server.list_tools()
    async def _list_tools() -> list[Tool]:
        return await list_tools()

    @mcp_server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        result = await call_tool(ctx, name, arguments)
        return [TextContent(type="text", text=result)]

    session_manager = StreamableHTTPSessionManager(app=mcp_server)

    # StreamableHTTPSessionManager.handle_request requires its internal
    # anyio task group to already be running (entered via `async with
    # session_manager.run():`), and anyio requires a task group be
    # entered and exited by the *same task* -- it must not outlive the
    # task that entered it. A real deployment enters it during the ASGI
    # lifespan's startup phase (see `lifespan` below), in uvicorn's own
    # long-lived lifespan task, which always runs before the first
    # request. Some test harnesses (e.g. Starlette's TestClient used
    # without a `with` block) never trigger ASGI lifespan events at all,
    # so `_ensure_session_manager_started` also lazily starts it on
    # first request -- but in its own dedicated background task (not
    # the request-handling task, which would otherwise return while the
    # task group it entered is still open, corrupting anyio's cancel
    # scope nesting for that task). Idempotent either way, guarded by a
    # lock against concurrent first requests racing.
    _start_lock = asyncio.Lock()
    _started = asyncio.Event()
    _stop = asyncio.Event()
    _runner_task: asyncio.Task | None = None

    async def _run_session_manager() -> None:
        async with session_manager.run():
            _started.set()
            await _stop.wait()

    async def _ensure_session_manager_started() -> None:
        nonlocal _runner_task
        if _started.is_set():
            return
        async with _start_lock:
            if _started.is_set():
                return
            _runner_task = asyncio.create_task(_run_session_manager())
            await _started.wait()

    async def _stop_session_manager() -> None:
        if _runner_task is None:
            return
        _stop.set()
        await _runner_task

    class _MCPEndpoint:
        """Raw ASGI callable, not a Starlette Request/Response-style
        endpoint: StreamableHTTPSessionManager.handle_request writes its
        response directly onto `send` itself, so wrapping this in a
        plain function endpoint (which Starlette's Route treats as
        `func(request) -> response` and double-sends) would break it.
        A class instance's __call__ is what Route's endpoint-vs-ASGI-app
        detection (inspect.isfunction/ismethod) treats as a raw ASGI
        app instead."""

        async def __call__(self, scope, receive, send):
            credentials = load_credentials(credentials_path)
            token = _extract_bearer_token(scope.get("headers", []))
            identity = find_identity(token, credentials) if token else None
            if identity is None:
                response = JSONResponse({"error": "unauthorized"}, status_code=401)
                await response(scope, receive, send)
                return

            await _ensure_session_manager_started()

            ctx.remote_identity = identity
            session_id = f"remote:{identity.credential_id}"
            var_token = set_current_session_id(session_id)
            try:
                await session_manager.handle_request(scope, receive, send)
            finally:
                reset_current_session_id(var_token)
                ctx.remote_identity = None

    @asynccontextmanager
    async def lifespan(app: Starlette):
        await _ensure_session_manager_started()
        try:
            yield
        finally:
            await _stop_session_manager()

    return Starlette(routes=[Route("/mcp", _MCPEndpoint(), methods=["GET", "POST", "DELETE"])],
                      lifespan=lifespan)


def run_http_server(ctx: Any, host: str = "127.0.0.1", port: int = 8766,
                     credentials_path: str = "config/mcp_auth.yaml") -> None:
    """Blocking entry point -- call from server.py's sync_main() when
    PROMPTWISE_TRANSPORT=http. Fails loudly on startup error (e.g. port
    already in use); never silently falls back to stdio."""
    import uvicorn
    app = build_app(ctx, credentials_path=credentials_path)
    uvicorn.run(app, host=host, port=port)
