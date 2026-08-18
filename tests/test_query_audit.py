"""WP1 1c -- AuditLog.query(): streaming, filterable audit query."""
from promptwise.core.audit_log import AuditLog


def _seed(log, n=5):
    for i in range(n):
        log.append(
            f"task-{i}", actor="alice" if i % 2 == 0 else "bob",
            agent="claude-code", gate_decision="PASS" if i < 3 else "FAIL")


def test_query_no_filter_returns_all(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed(log)
    assert len(log.query()) == 5


def test_query_filters_by_actor(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed(log)
    out = log.query(actor="alice")
    assert all(r["actor"] == "alice" for r in out)
    assert len(out) == 3


def test_query_filters_by_gate_decision(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed(log)
    out = log.query(gate_decision="FAIL")
    assert len(out) == 2


def test_query_respects_limit_most_recent_first(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed(log)
    out = log.query(limit=2)
    assert len(out) == 2
    assert out[0]["task"] == "task-4"
    assert out[1]["task"] == "task-3"


def test_query_since_until_bounds(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed(log)
    all_recs = log.query()
    mid_ts = all_recs[2]["timestamp"]
    out = log.query(since=mid_ts)
    assert all(r["timestamp"] >= mid_ts for r in out)


def test_query_does_not_load_full_file_at_once(tmp_path, monkeypatch):
    # Streaming guard: read_text().splitlines() must not be used by query().
    log = AuditLog(tmp_path / "audit.jsonl")
    _seed(log, n=3)

    from pathlib import Path
    original_read_text = Path.read_text

    def _blow_up_if_called_by_query(self, *a, **k):
        import traceback
        stack = traceback.extract_stack()
        if any(f.name == "query" for f in stack):
            raise AssertionError("query() must not use Path.read_text() (streaming required)")
        return original_read_text(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", _blow_up_if_called_by_query)
    log.query()


# ── MCP tool handler ─────────────────────────────────────────────────────────
import asyncio
import json as _json
import typing

from promptwise.core.tool_registry import ServerContext
import promptwise.server  # noqa: F401 -- import server first so its own module-import
# order (not whatever order pytest happens to collect test files in) decides
# _TOOL_DEFS' registration order; importing handlers.policy_intel directly
# without this can register its tools "early" if this test module is
# collected before anything else imports promptwise.server, which then
# reorders _TOOL_DEFS and breaks test_tool_registry_snapshot.py's golden
# ordering check in a full-suite run.
from promptwise.handlers.policy_intel import _handle_query_audit

# None is a valid stand-in for ctx here: this handler never reads ctx (see
# tests/test_approvals.py's _CTX for the established convention). A real
# ServerContext is a 22-field dataclass with no defaults, so ServerContext()
# itself is not constructible.
_CTX = typing.cast(ServerContext, None)


def test_query_audit_tool(tmp_path, monkeypatch):
    def _fake_get_audit_log():
        return AuditLog(tmp_path / "audit.jsonl")

    log = _fake_get_audit_log()
    _seed(log)
    monkeypatch.setattr(
        "promptwise.handlers.policy_intel._get_audit_log", _fake_get_audit_log)
    out = _json.loads(asyncio.run(_handle_query_audit(_CTX, {"actor": "alice"})))
    assert out["count"] == 3
    assert all(r["actor"] == "alice" for r in out["records"])


# ── WP1 1c -- opt-in PII-redacted prompt capture ─────────────────────────────
def test_append_without_capture_flag_stores_nothing(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    rec = log.append("task", prompt_text="my email is a@b.com", capture_prompts=False)
    assert rec.prompt_capture == ""


def test_append_with_capture_flag_stores_redacted_text(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    rec = log.append("task", prompt_text="my email is a@b.com", capture_prompts=True)
    assert rec.prompt_capture != ""
    assert "a@b.com" not in rec.prompt_capture


def test_append_with_capture_flag_but_no_prompt_text_stores_nothing(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    rec = log.append("task", capture_prompts=True)
    assert rec.prompt_capture == ""
