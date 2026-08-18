"""WP1 1c -- AuditLog.compact(): archive expired records, re-anchor chain."""
import time

from promptwise.core.audit_log import AuditLog, GENESIS


def _seed_with_ages(log, ages_days):
    # append() always stamps "now"; to test retention we monkeypatch time
    # per-record by writing records directly and re-persisting, mirroring
    # append()'s own hash-chain construction so the test fixture is a real
    # valid chain, not a shortcut.
    import promptwise.core.audit_log as al
    real_strftime, real_gmtime = time.strftime, time.gmtime
    for i, age in enumerate(ages_days):
        fake_now = time.time() - age * 86400

        class _FrozenTime:
            @staticmethod
            def strftime(fmt, _t):
                return real_strftime(fmt, real_gmtime(fake_now))

            @staticmethod
            def gmtime(_=None):
                return real_gmtime(fake_now)

        orig_strftime, orig_gmtime = al.time.strftime, al.time.gmtime
        al.time.strftime = _FrozenTime.strftime
        al.time.gmtime = _FrozenTime.gmtime
        try:
            log.append(f"task-{i}", actor="alice")
        finally:
            al.time.strftime, al.time.gmtime = orig_strftime, orig_gmtime


def test_compact_archives_expired_keeps_recent(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed_with_ages(log, [40, 35, 10, 1])  # first two older than 30-day retention
    result = log.compact(retention_days=30)
    assert result["archived_count"] == 2
    assert result["kept_count"] == 2


def test_compact_live_chain_verifies_after_compaction(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed_with_ages(log, [40, 35, 10, 1])
    log.compact(retention_days=30)
    reloaded = AuditLog(tmp_path / "audit.jsonl")
    ok, msg = reloaded.verify()
    assert ok, msg
    assert reloaded.records[0].task == "compaction"
    assert reloaded.records[0].prev_hash == GENESIS


def test_compact_archive_file_written_and_contains_expired_records(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed_with_ages(log, [40, 35, 10, 1])
    result = log.compact(retention_days=30)
    archive_path = tmp_path / result["archive_path"]
    lines = archive_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    import json
    tasks = {json.loads(l)["task"] for l in lines}
    assert tasks == {"task-0", "task-1"}


def test_compact_noop_when_nothing_expired(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed_with_ages(log, [1, 2])
    result = log.compact(retention_days=30)
    assert result["archived_count"] == 0
    assert result["archive_path"] is None
    ok, msg = log.verify()
    assert ok, msg


def test_compact_preserves_prompt_capture_on_kept_records(tmp_path):
    # WP1 1c -- compact() reconstructs kept records field-by-field; it must
    # carry over prompt_capture (set via append(capture_prompts=True)) rather
    # than silently dropping back to the AuditRecord default "". This record
    # is stamped "now" (not backdated), so it's always a *kept* record.
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append("recent-captured", capture_prompts=True, prompt_text="contact me at x@y.com")
    _seed_with_ages(log, [40])  # one old record, so compact() has something to expire
    result = log.compact(retention_days=30)
    assert result["archived_count"] == 1
    assert result["kept_count"] == 1
    reloaded = AuditLog(tmp_path / "audit.jsonl")
    captured = [r for r in reloaded.records if r.prompt_capture]
    assert captured, "prompt_capture must survive compact()'s reindexing of kept records"
    assert "x@y.com" not in captured[0].prompt_capture


def test_compact_retention_zero_disables_compaction(tmp_path):
    # retention_days=0 means "never compact" per config default -- compact()
    # itself still supports being called explicitly with 0, but the tool
    # handler (Task 8) is what actually enforces the "0 = disabled" no-op.
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed_with_ages(log, [400])
    result = log.compact(retention_days=0)
    assert result["archived_count"] == 1  # compact() itself takes retention literally


# ── MCP tool handler ─────────────────────────────────────────────────────────
import asyncio
import json as _json
import typing

from promptwise.core.tool_registry import ServerContext
import promptwise.server  # noqa: F401 -- see tests/test_query_audit.py's comment:
# import server first so its own module-import order decides _TOOL_DEFS'
# registration order, avoiding a collection-order-dependent golden-snapshot
# break in test_tool_registry_snapshot.py.
from promptwise.handlers.policy_intel import _handle_compact_audit

# None is a valid stand-in for ctx here: this handler never reads ctx (see
# tests/test_approvals.py's _CTX for the established convention). A real
# ServerContext is a 22-field dataclass with no defaults, so ServerContext()
# itself is not constructible.
_CTX = typing.cast(ServerContext, None)


def test_compact_audit_tool(tmp_path, monkeypatch):
    def _fake_get_audit_log():
        return AuditLog(tmp_path / "audit.jsonl")

    log = _fake_get_audit_log()
    _seed_with_ages(log, [400, 1])
    monkeypatch.setattr(
        "promptwise.handlers.policy_intel._get_audit_log", _fake_get_audit_log)
    out = _json.loads(asyncio.run(_handle_compact_audit(_CTX, {"retention_days": 30})))
    assert out["archived_count"] == 1
    assert out["kept_count"] == 1


def test_compact_audit_tool_retention_zero_is_noop(tmp_path, monkeypatch):
    def _fake_get_audit_log():
        return AuditLog(tmp_path / "audit.jsonl")

    log = _fake_get_audit_log()
    _seed_with_ages(log, [400])
    monkeypatch.setattr(
        "promptwise.handlers.policy_intel._get_audit_log", _fake_get_audit_log)
    out = _json.loads(asyncio.run(_handle_compact_audit(_CTX, {"retention_days": 0})))
    assert out["archived_count"] == 0
    assert out.get("skipped") == "retention_days=0 disables compaction"
