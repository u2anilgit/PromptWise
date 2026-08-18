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


def test_compact_retention_zero_disables_compaction(tmp_path):
    # retention_days=0 means "never compact" per config default -- compact()
    # itself still supports being called explicitly with 0, but the tool
    # handler (Task 8) is what actually enforces the "0 = disabled" no-op.
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed_with_ages(log, [400])
    result = log.compact(retention_days=0)
    assert result["archived_count"] == 1  # compact() itself takes retention literally
