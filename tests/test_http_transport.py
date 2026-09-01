import asyncio

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
    client = TestClient(app)
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert r.status_code == 401


def test_invalid_token_is_rejected(tmp_path):
    cred_path = tmp_path / "mcp_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: admin\n",
        encoding="utf-8")
    app = build_app(_minimal_ctx(), credentials_path=str(cred_path))
    client = TestClient(app)
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                     headers={"Authorization": "Bearer wrong-value"})
    assert r.status_code == 401


def test_no_credentials_file_rejects_every_token(tmp_path):
    missing = tmp_path / "does_not_exist.yaml"
    app = build_app(_minimal_ctx(), credentials_path=str(missing))
    client = TestClient(app)
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
    client = TestClient(app)
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                     headers={"Authorization": "Bearer abc"})
    assert r.status_code != 401
