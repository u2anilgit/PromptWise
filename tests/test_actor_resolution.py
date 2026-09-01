from promptwise.core.identity import Identity, resolved_actor
from promptwise.core.tool_registry import ServerContext
import dataclasses


def test_server_context_has_identity_field():
    fields = {f.name for f in dataclasses.fields(ServerContext)}
    assert "identity" in fields


def test_agile_check_policy_uses_identity_when_actor_omitted(tmp_path, monkeypatch):
    import asyncio
    from promptwise.core.audit_log import AuditLog
    import promptwise.handlers.agile as agile_mod

    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(agile_mod, "_get_audit_log", lambda: AuditLog(audit_path))
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("banned_operations: []\n", encoding="utf-8")

    class _FakeCtx:
        identity = Identity(username="jdoe", domain="CORP", groups=[], email="", source="env")

    async def _run():
        return await agile_mod._handle_check_policy(
            _FakeCtx(), {"operation": "deploy", "record_to_audit": True, "policy_path": str(policy_path)})

    asyncio.run(_run())
    log = AuditLog(audit_path)
    assert log.records[-1].actor == "jdoe"


def test_agile_check_policy_explicit_actor_overrides_identity(tmp_path, monkeypatch):
    import asyncio
    from promptwise.core.audit_log import AuditLog
    import promptwise.handlers.agile as agile_mod

    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(agile_mod, "_get_audit_log", lambda: AuditLog(audit_path))
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("banned_operations: []\n", encoding="utf-8")

    class _FakeCtx:
        identity = Identity(username="jdoe", domain="CORP", groups=[], email="", source="env")

    async def _run():
        return await agile_mod._handle_check_policy(
            _FakeCtx(), {"operation": "deploy", "record_to_audit": True, "actor": "ci-bot",
                         "policy_path": str(policy_path)})

    asyncio.run(_run())
    log = AuditLog(audit_path)
    assert log.records[-1].actor == "ci-bot"


def test_agile_record_audit_uses_identity_when_actor_omitted(tmp_path, monkeypatch):
    import asyncio
    from promptwise.core.audit_log import AuditLog
    import promptwise.handlers.agile as agile_mod

    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(agile_mod, "_get_audit_log", lambda: AuditLog(audit_path))

    class _FakeCtx:
        identity = Identity(username="jdoe", domain="CORP", groups=[], email="", source="env")

    async def _run():
        return await agile_mod._handle_record_audit(_FakeCtx(), {"task": "did a thing"})

    asyncio.run(_run())
    log = AuditLog(audit_path)
    assert log.records[-1].actor == "jdoe"


def test_agile_record_audit_explicit_actor_overrides_identity(tmp_path, monkeypatch):
    import asyncio
    from promptwise.core.audit_log import AuditLog
    import promptwise.handlers.agile as agile_mod

    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(agile_mod, "_get_audit_log", lambda: AuditLog(audit_path))

    class _FakeCtx:
        identity = Identity(username="jdoe", domain="CORP", groups=[], email="", source="env")

    async def _run():
        return await agile_mod._handle_record_audit(
            _FakeCtx(), {"task": "did a thing", "actor": "ci-bot"})

    asyncio.run(_run())
    log = AuditLog(audit_path)
    assert log.records[-1].actor == "ci-bot"
