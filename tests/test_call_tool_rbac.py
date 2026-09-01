import asyncio
import json

from promptwise.core.session_context import set_current_remote_identity, reset_current_remote_identity
from promptwise.dashboard.auth import Identity
from promptwise.server import call_tool


class _FakeCtx:
    """A minimal stand-in ServerContext -- call_tool only needs `ctx` to
    hand to whatever handler actually gets dispatched, and these tests
    target tools trivial enough not to need real services."""
    pass


def test_stdio_no_remote_identity_allows_every_tool_regardless_of_role():
    """No remote identity set (the stdio/local case) -- RBAC is skipped
    entirely, even for an admin-only tool."""
    async def _run():
        return await call_tool(_FakeCtx(), "set_feature_flag", {"flag": "test", "value": True})
    result = json.loads(asyncio.run(_run()))
    assert result.get("type") != "PermissionDenied"


def test_remote_viewer_denied_on_admin_only_tool():
    identity = Identity(credential_id="abc123def456", role="viewer", projects=None)
    token = set_current_remote_identity(identity)
    try:
        async def _run():
            return await call_tool(_FakeCtx(), "set_feature_flag", {"flag": "test", "value": True})
        result = json.loads(asyncio.run(_run()))
        assert result["type"] == "PermissionDenied"
        assert result["tool"] == "set_feature_flag"
    finally:
        reset_current_remote_identity(token)


def test_remote_viewer_allowed_on_viewer_safe_tool():
    identity = Identity(credential_id="abc123def456", role="viewer", projects=None)
    token = set_current_remote_identity(identity)
    try:
        async def _run():
            return await call_tool(_FakeCtx(), "list_tasks", {})
        result = json.loads(asyncio.run(_run()))
        assert result.get("type") != "PermissionDenied"
    finally:
        reset_current_remote_identity(token)


def test_remote_admin_allowed_on_admin_only_tool():
    identity = Identity(credential_id="abc123def456", role="admin", projects=None)
    token = set_current_remote_identity(identity)
    try:
        async def _run():
            return await call_tool(_FakeCtx(), "set_feature_flag", {"flag": "test", "value": True})
        result = json.loads(asyncio.run(_run()))
        assert result.get("type") != "PermissionDenied"
    finally:
        reset_current_remote_identity(token)


def test_denied_call_is_recorded_to_audit_log(tmp_path, monkeypatch):
    from promptwise.core.audit_log import AuditLog
    import promptwise.core.tool_registry as tool_registry_mod

    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(tool_registry_mod, "_get_audit_log", lambda: AuditLog(audit_path))

    identity = Identity(credential_id="abc123def456", role="viewer", projects=None)
    token = set_current_remote_identity(identity)
    try:
        async def _run():
            return await call_tool(_FakeCtx(), "set_feature_flag", {"flag": "test", "value": True})
        asyncio.run(_run())
    finally:
        reset_current_remote_identity(token)

    log = AuditLog(audit_path)
    assert len(log.records) == 1
    assert log.records[-1].actor == "abc123def456"
    assert log.records[-1].gate_decision == "FAIL"
