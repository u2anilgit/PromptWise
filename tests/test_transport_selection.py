"""tests.test_transport_selection -- coverage for sync_main()'s
PROMPTWISE_TRANSPORT gate (src/promptwise/server.py), which was
previously entirely untested (see final review of
docs/superpowers/plans/2026-09-01-remote-mcp-transport.md). Follows this
codebase's monkeypatch-only testing convention -- no unittest.mock."""
import asyncio

import promptwise.server as server_mod


def test_default_transport_runs_stdio_main(monkeypatch):
    """No PROMPTWISE_TRANSPORT set at all -> the stdio main() coroutine is
    what asyncio.run() actually executes, not the http path."""
    monkeypatch.delenv("PROMPTWISE_TRANSPORT", raising=False)
    calls = []

    async def _fake_main():
        calls.append("main")

    async def _fake_build_context():
        calls.append("_build_context")
        return object()

    def _fake_run_http_server(*args, **kwargs):
        calls.append("run_http_server")

    monkeypatch.setattr(server_mod, "main", _fake_main)
    monkeypatch.setattr(server_mod, "_build_context", _fake_build_context)
    import promptwise.transports.http_server as http_server_mod
    monkeypatch.setattr(http_server_mod, "run_http_server", _fake_run_http_server)

    server_mod.sync_main()

    assert calls == ["main"]


def test_explicit_stdio_transport_runs_stdio_main(monkeypatch):
    """PROMPTWISE_TRANSPORT=stdio (explicit) behaves identically to unset."""
    monkeypatch.setenv("PROMPTWISE_TRANSPORT", "stdio")
    calls = []

    async def _fake_main():
        calls.append("main")

    monkeypatch.setattr(server_mod, "main", _fake_main)

    server_mod.sync_main()

    assert calls == ["main"]


def test_http_transport_invokes_run_http_server_with_env_derived_args(monkeypatch, tmp_path):
    """PROMPTWISE_TRANSPORT=http -> run_http_server is invoked (not
    main()/stdio) with host/port/credentials_path derived from the env
    vars, and the credentials_path is resolved to an absolute path."""
    cred_path = tmp_path / "mcp_auth.yaml"
    cred_path.write_text("entries: []\n", encoding="utf-8")

    monkeypatch.setenv("PROMPTWISE_TRANSPORT", "http")
    monkeypatch.setenv("PROMPTWISE_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("PROMPTWISE_HTTP_PORT", "9999")
    monkeypatch.setenv("PROMPTWISE_MCP_CREDENTIALS_PATH", str(cred_path))

    calls = []
    sentinel_ctx = object()

    async def _fake_build_context():
        return sentinel_ctx

    async def _fake_main():
        calls.append("main")

    def _fake_run_http_server(ctx, host=None, port=None, credentials_path=None):
        calls.append(("run_http_server", ctx, host, port, credentials_path))

    monkeypatch.setattr(server_mod, "main", _fake_main)
    monkeypatch.setattr(server_mod, "_build_context", _fake_build_context)
    import promptwise.transports.http_server as http_server_mod
    monkeypatch.setattr(http_server_mod, "run_http_server", _fake_run_http_server)

    server_mod.sync_main()

    assert len(calls) == 1
    label, ctx, host, port, credentials_path = calls[0]
    assert label == "run_http_server"
    assert ctx is sentinel_ctx
    assert host == "0.0.0.0"
    assert port == 9999
    assert credentials_path == str(cred_path)


def test_unrecognized_transport_raises(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_TRANSPORT", "garbage")
    try:
        server_mod.sync_main()
        assert False, "expected ValueError"
    except ValueError as e:
        assert "garbage" in str(e)


def test_empty_transport_falls_back_to_stdio_without_raising(monkeypatch):
    """PROMPTWISE_TRANSPORT="" (explicitly empty, a common accident in
    .env/compose files) must fall back to stdio, not raise."""
    monkeypatch.setenv("PROMPTWISE_TRANSPORT", "")
    calls = []

    async def _fake_main():
        calls.append("main")

    monkeypatch.setattr(server_mod, "main", _fake_main)

    server_mod.sync_main()

    assert calls == ["main"]
