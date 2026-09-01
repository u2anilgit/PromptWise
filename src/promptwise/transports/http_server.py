"""transports.http_server -- optional Streamable HTTP MCP transport.

Alongside (never replacing) server.py's stdio entrypoint. Selected via
PROMPTWISE_TRANSPORT=http (default stdio, zero behavior change for
existing users). Auth is fail-closed: a missing or invalid Bearer token
never reaches the MCP session manager -- see
docs/superpowers/specs/2026-09-01-remote-mcp-transport-design.md.

Session identity, and what "per-request" actually means here: the
session_id and remote Identity are set on their own contextvars.ContextVar
(core/session_context.py) around every call into
session_manager.handle_request, and reset afterward -- but the MCP SDK's
StreamableHTTPSessionManager, for an existing (already-`initialize`d)
session, dispatches the request to that session's own long-lived task
(spawned once, at session-creation time, inside the `initialize` request's
handling). asyncio tasks snapshot their contextvars once, at task-creation
time. So in practice the set/reset in _MCPEndpoint.__call__ only actually
determines the session_id/remote_identity that session's *tool-call
handling* task observes on its *first* request (the one that created the
session); the set/reset on every later request to that same session is a
correctness-neutral no-op as far as that task's own contextvar snapshot
goes. Identity is NOT re-validated by the SDK on every individual request
within an established session -- it is fixed once, at session-creation
time.

That's exactly why session-hijacking has to be enforced separately, at
the HTTP layer, rather than relying on per-request contextvar
re-validation: `_session_owners` below (a plain dict in `build_app`,
{mcp_session_id: credential_id}) records which credential created each
session (captured off the `mcp-session-id` response header the SDK
returns when a new session is created) and rejects (404, matching the
SDK's own "session not found" response shape) any later request that
presents an existing session id under a *different* credential -- before
that request ever reaches session_manager.handle_request. See
tests/test_http_transport.py's
test_second_token_cannot_reuse_first_tokens_session for the property
this exists to guarantee.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from promptwise.dashboard.auth import find_identity, load_credentials
from promptwise.core.session_context import (
    set_current_session_id, reset_current_session_id,
    set_current_remote_identity, reset_current_remote_identity,
)


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


def _extract_header(headers: list[tuple[bytes, bytes]], name: str) -> str | None:
    """Raw ASGI header list -> the decoded value of one header (case
    -insensitive), or None if absent."""
    target = name.lower().encode("latin-1")
    for header_name, value in headers:
        if header_name.lower() == target:
            return value.decode("latin-1")
    return None


async def _session_not_found_response(scope, receive, send) -> None:
    """The exact response StreamableHTTPSessionManager itself sends for an
    unknown/invalid mcp-session-id -- reused here (rather than inventing a
    new shape) for a *known* session id whose recorded owner credential
    doesn't match the caller's, so a hijack attempt is indistinguishable
    from the session simply not existing."""
    from mcp.types import INVALID_REQUEST, ErrorData, JSONRPCError
    body = JSONRPCError(jsonrpc="2.0", id="server-error",
                         error=ErrorData(code=INVALID_REQUEST, message="Session not found"))
    response = Response(body.model_dump_json(by_alias=True, exclude_none=True),
                         status_code=404, media_type="application/json")
    await response(scope, receive, send)


def build_app(ctx: Any, credentials_path: str = "config/mcp_auth.yaml") -> Starlette:
    """Build the Starlette app. `ctx` is the ServerContext the existing
    call_tool(ctx, name, arguments) dispatch already uses -- shared
    across all connections (memory/router/etc. are process-wide
    services; session_id and remote_identity are per-connection, carried
    via contextvars rather than on `ctx` itself -- see module docstring)."""
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

    # Identity of the credential that created each mcp-session-id, keyed
    # by that session id. A plain in-memory dict, scoped to this app
    # instance's lifetime -- no persistence needed (a restart drops all
    # sessions anyway, on both the MCP SDK's own session tracking and
    # ours). Captured off the `mcp-session-id` response header the SDK
    # returns when _MCPEndpoint.__call__ dispatches a request that
    # creates a new session (see `_capturing_send` below); consulted
    # before dispatching any request that carries an *existing*
    # mcp-session-id, to reject a different credential trying to reuse
    # someone else's session (see module docstring for why this can't be
    # done via per-request contextvar re-validation alone).
    _session_owners: dict[str, str] = {}

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

            incoming_session_id = _extract_header(scope.get("headers", []), "mcp-session-id")
            if incoming_session_id is not None:
                owner_credential_id = _session_owners.get(incoming_session_id)
                if owner_credential_id is not None and owner_credential_id != identity.credential_id:
                    # A different (still-valid) credential is trying to
                    # reuse a session it didn't create -- reject before
                    # this ever reaches the MCP session manager. Same
                    # response shape as an unknown session id: a hijack
                    # attempt must be indistinguishable from "no such
                    # session" to the caller.
                    await _session_not_found_response(scope, receive, send)
                    return

            session_id = f"remote:{identity.credential_id}"
            session_token = set_current_session_id(session_id)
            identity_token = set_current_remote_identity(identity)

            async def _capturing_send(message):
                if message.get("type") == "http.response.start":
                    header_value = _extract_header(message.get("headers") or [], "mcp-session-id")
                    # A brand-new session was created by this request (the
                    # response carries a fresh mcp-session-id this request
                    # didn't already have) -- record its owner *before*
                    # the response is actually sent to the client, so the
                    # window between the client observing the session id
                    # and the server recording its owner is as narrow as
                    # possible (rather than only after handle_request
                    # returns).
                    if header_value is not None and incoming_session_id is None:
                        _session_owners[header_value] = identity.credential_id
                await send(message)

            try:
                await session_manager.handle_request(scope, receive, _capturing_send)
            finally:
                reset_current_remote_identity(identity_token)
                reset_current_session_id(session_token)

    @asynccontextmanager
    async def lifespan(app: Starlette):
        # The MCP SDK's StreamableHTTPSessionManager requires its internal
        # anyio task group to already be running (entered via `async with
        # session_manager.run():`) before handle_request is ever called.
        # ASGI lifespan is the right place for this -- uvicorn always
        # drives it before the first request, and Starlette's TestClient
        # drives it too when used as `with TestClient(app) as client:`
        # (see tests/test_http_transport.py).
        async with session_manager.run():
            yield

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
