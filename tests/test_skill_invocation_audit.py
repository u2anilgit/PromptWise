"""invoke_skill/skill_chain already return real per-call cost/model data
(execute_skill's response has model_used/input_tokens/output_tokens/cost_usd)
but neither handler ever persisted it -- cost_logs and the audit trail never
saw a skill invocation. Both handlers must now log cost and append an audit
record for each successful skill execution, without changing what they
return to the caller."""
import asyncio
import json
import typing

import promptwise.server as s
from promptwise.core.audit_log import AuditLog


class _FakeSkill:
    name = "demo-skill"


class _FakeSkillLoader:
    def __init__(self, skill):
        self._skill = skill

    def get_skill(self, name):
        return self._skill if name == self._skill.name else None


class _FakeOrchestrator:
    def __init__(self, result):
        self._result = result

    async def execute_skill(self, skill, context, router=None):
        return self._result

    async def execute_skill_chain(self, skill_loader, names, mode, context, router=None):
        return {"status": "completed", "ordered_execution": names,
                "results": {n: self._result for n in names}}


class _FakeMemory:
    def __init__(self):
        self.calls = []

    async def record_cost(self, **kwargs):
        self.calls.append(kwargs)


_RESULT = {"status": "success", "skill": "demo-skill", "model_used": "claude-x",
           "result": "ok", "input_tokens": 10, "output_tokens": 20, "cost_usd": 0.5}


def test_invoke_skill_logs_cost_and_audit(monkeypatch, tmp_path):
    class _FakeCtx:
        skill_loader = _FakeSkillLoader(_FakeSkill())
        orchestrator = _FakeOrchestrator(_RESULT)
        router = None
        memory = _FakeMemory()

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(s, "_get_audit_log", lambda: AuditLog(audit_path))

    out = asyncio.run(s._handle_invoke_skill(ctx, {"skill_name": "demo-skill"}))

    assert json.loads(out) == _RESULT  # return value unchanged
    assert ctx.memory.calls and ctx.memory.calls[0]["cost_usd"] == 0.5
    assert audit_path.exists()
    assert "demo-skill" in audit_path.read_text(encoding="utf-8")


def test_skill_chain_logs_cost_and_audit_per_skill(monkeypatch, tmp_path):
    class _FakeCtx:
        skill_loader = _FakeSkillLoader(_FakeSkill())
        orchestrator = _FakeOrchestrator(_RESULT)
        router = None
        memory = _FakeMemory()

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(s, "_get_audit_log", lambda: AuditLog(audit_path))

    asyncio.run(s._handle_skill_chain(ctx, {"skills": ["demo-skill", "demo-skill-2"]}))

    assert len(ctx.memory.calls) == 2
    assert audit_path.exists()


def test_failed_skill_execution_does_not_log_cost(monkeypatch, tmp_path):
    failed = {"status": "error", "error": "boom", "skill": "demo-skill"}

    class _FakeCtx:
        skill_loader = _FakeSkillLoader(_FakeSkill())
        orchestrator = _FakeOrchestrator(failed)
        router = None
        memory = _FakeMemory()

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    monkeypatch.setattr(s, "_get_audit_log", lambda: AuditLog(tmp_path / "audit.jsonl"))

    asyncio.run(s._handle_invoke_skill(ctx, {"skill_name": "demo-skill"}))
    assert ctx.memory.calls == []


def test_skill_chain_mixed_success_and_failure_logs_only_success(monkeypatch, tmp_path):
    ok = _RESULT
    failed = {"status": "error", "error": "boom", "skill": "bad-skill"}

    class _MixedOrchestrator:
        async def execute_skill_chain(self, skill_loader, names, mode, context, router=None):
            return {"status": "completed", "ordered_execution": names,
                    "results": {"demo-skill": ok, "bad-skill": failed}}

    class _FakeCtx:
        skill_loader = _FakeSkillLoader(_FakeSkill())
        orchestrator = _MixedOrchestrator()
        router = None
        memory = _FakeMemory()

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(s, "_get_audit_log", lambda: AuditLog(audit_path))

    asyncio.run(s._handle_skill_chain(ctx, {"skills": ["demo-skill", "bad-skill"]}))

    assert len(ctx.memory.calls) == 1
    assert ctx.memory.calls[0]["cost_usd"] == 0.5
    text = audit_path.read_text(encoding="utf-8")
    assert "demo-skill" in text
    assert "bad-skill" not in text


def test_record_skill_execution_is_fail_open_when_record_cost_raises(monkeypatch, tmp_path):
    class _RaisingMemory:
        async def record_cost(self, **kwargs):
            raise RuntimeError("db down")

    class _FakeCtx:
        skill_loader = _FakeSkillLoader(_FakeSkill())
        orchestrator = _FakeOrchestrator(_RESULT)
        router = None
        memory = _RaisingMemory()

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(s, "_get_audit_log", lambda: AuditLog(audit_path))

    out = asyncio.run(s._handle_invoke_skill(ctx, {"skill_name": "demo-skill"}))

    assert json.loads(out) == _RESULT  # return value unaffected despite record_cost raising
    # audit log write still happens even though cost logging failed
    assert audit_path.exists()
    assert "demo-skill" in audit_path.read_text(encoding="utf-8")
