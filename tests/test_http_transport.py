import dataclasses
import json

from starlette.testclient import TestClient

from promptwise.core.tool_registry import ServerContext
from promptwise.dashboard.auth import hash_credential
from promptwise.transports.http_server import build_app


def _minimal_ctx() -> ServerContext:
    """A ServerContext with every field as a bare stand-in -- this test
    suite only exercises the auth/routing layer, never real tool
    execution, so nothing here needs to be a working instance."""
    from types import SimpleNamespace
    return SimpleNamespace()  # duck-typed; build_app only needs ctx for _call_tool's closure


def test_missing_authorization_header_is_rejected(tmp_path):
    cred_path = tmp_path / "mcp_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: admin\n",
        encoding="utf-8")
    app = build_app(_minimal_ctx(), credentials_path=str(cred_path))
    with TestClient(app) as client:
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert r.status_code == 401


def test_invalid_token_is_rejected(tmp_path):
    cred_path = tmp_path / "mcp_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: admin\n",
        encoding="utf-8")
    app = build_app(_minimal_ctx(), credentials_path=str(cred_path))
    with TestClient(app) as client:
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                         headers={"Authorization": "Bearer wrong-value"})
        assert r.status_code == 401


def test_no_credentials_file_rejects_every_token(tmp_path):
    missing = tmp_path / "does_not_exist.yaml"
    app = build_app(_minimal_ctx(), credentials_path=str(missing))
    with TestClient(app) as client:
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                         headers={"Authorization": "Bearer anything"})
        assert r.status_code == 401


def test_valid_token_reaches_the_session_manager(tmp_path):
    """A valid token must pass the auth gate and reach the MCP session
    manager (proven by getting PAST 401 -- the session manager's own
    response code/shape for a bare POST without a prior initialize
    handshake is an MCP-protocol concern, not this auth layer's)."""
    cred_path = tmp_path / "mcp_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: admin\n",
        encoding="utf-8")
    app = build_app(_minimal_ctx(), credentials_path=str(cred_path))
    with TestClient(app) as client:
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                         headers={"Authorization": "Bearer abc"})
        assert r.status_code != 401


def _init_body(request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0", "id": request_id, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0"},
        },
    }


def test_second_token_cannot_reuse_first_tokens_session(tmp_path):
    """CRITICAL security property: a session belongs to the credential
    that created it. A different (still individually valid) Bearer token
    presenting an existing mcp-session-id must be refused -- not silently
    processed and audited as if it were the session's original owner.

    Live-reproduced before the fix: token B's request came back 200 and
    was actually dispatched under token A's session. The fix rejects it
    with 404 (matching StreamableHTTPSessionManager's own "session not
    found" response shape for a session id it doesn't recognize), before
    the request ever reaches session_manager.handle_request."""
    cred_path = tmp_path / "mcp_auth.yaml"
    cred_path.write_text(
        "entries:\n"
        "  - credential_hash: \"" + hash_credential("token-a") + "\"\n    role: admin\n"
        "  - credential_hash: \"" + hash_credential("token-b") + "\"\n    role: admin\n",
        encoding="utf-8")
    app = build_app(_minimal_ctx(), credentials_path=str(cred_path))
    with TestClient(app) as client:
        created = client.post(
            "/mcp", json=_init_body(1),
            headers={"Authorization": "Bearer token-a",
                     "Accept": "application/json, text/event-stream"})
        session_id = created.headers.get("mcp-session-id")
        assert session_id, "token A's initialize must create a session and return its id"

        hijack = client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers={"Authorization": "Bearer token-b",
                     "Accept": "application/json, text/event-stream",
                     "mcp-session-id": session_id})
        assert hijack.status_code == 404

        # The session's rightful owner can still use it afterward -- this
        # isn't a "session got wedged/terminated" side effect of the
        # rejection, only cross-credential reuse is blocked.
        legit = client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
            headers={"Authorization": "Bearer token-a",
                     "Accept": "application/json, text/event-stream",
                     "mcp-session-id": session_id})
        assert legit.status_code == 200


def _real_ctx() -> ServerContext:
    """A real ServerContext instance (unlike _minimal_ctx's bare
    SimpleNamespace) -- every field but `identity` is None (record_audit's
    handler never touches them), and `identity` is left at its real
    default_factory value (an anonymous core.identity.Identity with no
    username), so resolved_actor() falls through to the remote transport
    identity captured off the authenticated request."""
    fields = {f.name: None for f in dataclasses.fields(ServerContext) if f.name != "identity"}
    return ServerContext(**fields)


def test_record_audit_over_http_persists_record_with_resolved_actor(tmp_path, monkeypatch):
    """End-to-end: a real HTTP tools/call for record_audit, over the
    authenticated transport, resolves to a real persisted AuditRecord
    whose actor matches hash_credential(token)[:12] -- the property the
    final reviewer's own live probe proved but nothing in the suite
    checked."""
    from promptwise.core.audit_log import AuditLog
    import promptwise.handlers.agile as agile_mod

    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(agile_mod, "_get_audit_log", lambda: AuditLog(audit_path))

    token = "e2e-record-audit-token"
    cred_path = tmp_path / "mcp_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential(token) + "\"\n    role: admin\n",
        encoding="utf-8")

    app = build_app(_real_ctx(), credentials_path=str(cred_path))
    with TestClient(app) as client:
        init = client.post(
            "/mcp", json=_init_body(1),
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/json, text/event-stream"})
        session_id = init.headers.get("mcp-session-id")
        assert session_id

        call = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "record_audit", "arguments": {"task": "e2e http audit record"}}},
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/json, text/event-stream",
                     "mcp-session-id": session_id})
        assert call.status_code == 200

    log = AuditLog(audit_path)
    assert len(log.records) == 1
    rec = log.records[0]
    assert rec.task == "e2e http audit record"
    assert rec.actor == hash_credential(token)[:12]
