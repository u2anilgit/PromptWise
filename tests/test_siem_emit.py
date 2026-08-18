"""WP2 2c -- map detections/audit records to OCSF class dicts (primary)
and CEF lines (legacy); file-drop (default) or webhook emit. No SDKs --
dict mapping + json/str formatting only.
"""
import json

from promptwise.core.siem_emit import SiemEmitter, to_cef, to_ocsf


def _finding():
    return {"actor": "alice", "category": "novel_tool_sequence",
            "detail": "never-seen-before tool sequence", "threat_score": 85.5,
            "evidence": {"novel_bigrams": ["Bash->Bash"]}}


def test_to_ocsf_required_fields():
    event = to_ocsf(_finding())
    for field in ("class_uid", "category_uid", "activity_id", "severity_id", "time", "actor", "message"):
        assert field in event
    assert event["actor"]["user"]["name"] == "alice"
    assert event["message"] == "never-seen-before tool sequence"


def test_to_ocsf_severity_scales_with_threat_score():
    low = to_ocsf({**_finding(), "threat_score": 10.0})
    high = to_ocsf({**_finding(), "threat_score": 95.0})
    assert high["severity_id"] > low["severity_id"]


def test_to_cef_header_escaping():
    line = to_cef({**_finding(), "detail": "pipe|and=equals in detail"})
    assert line.startswith("CEF:0|PromptWise|")
    # CEF spec: pipes in extension values need not be escaped, but header
    # fields (before the final unescaped "|") must have "|" and "\\" escaped.
    assert "PromptWise" in line
    assert "threatScore=85" in line or "threatScore=85.5" in line


def test_siem_emitter_file_drop_writes_ocsf_jsonl(tmp_path):
    emitter = SiemEmitter(mode="file", drop_dir=tmp_path / "siem")
    result = emitter.emit(_finding())
    assert result["written"] is True
    path = tmp_path / "siem" / result["path"]
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["actor"]["user"]["name"] == "alice"


def test_siem_emitter_file_drop_appends_multiple_events(tmp_path):
    emitter = SiemEmitter(mode="file", drop_dir=tmp_path / "siem")
    emitter.emit(_finding())
    emitter.emit(_finding())
    result = emitter.emit(_finding())
    path = tmp_path / "siem" / result["path"]
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 3


def test_siem_emitter_webhook_mode_calls_sink(monkeypatch):
    calls = []

    class _FakeSink:
        def __init__(self, url, **kw):
            self.url = url

        def send(self, record):
            calls.append(record)
            return True

    monkeypatch.setattr("promptwise.core.siem_emit.WebhookSink", _FakeSink)
    emitter = SiemEmitter(mode="webhook", webhook_url="https://example.invalid/siem")
    result = emitter.emit(_finding())
    assert result["sent"] is True
    assert len(calls) == 1
    assert calls[0]["actor"]["user"]["name"] == "alice"


def test_siem_emitter_unknown_mode_defaults_to_file(tmp_path):
    emitter = SiemEmitter(mode="bogus", drop_dir=tmp_path / "siem")
    result = emitter.emit(_finding())
    assert result["mode"] == "file"


# ── MCP tool handler ─────────────────────────────────────────────────────────
import asyncio
import typing

from promptwise.core.tool_registry import ServerContext
import promptwise.server  # noqa: F401 -- import server first so its own module-import
# order (not whatever order pytest happens to collect test files in) decides
# _TOOL_DEFS' registration order; importing handlers.detection directly
# without this can register its tools "early" if this test module is
# collected before anything else imports promptwise.server, which then
# reorders _TOOL_DEFS and breaks test_tool_registry_snapshot.py's golden
# ordering check in a full-suite run.
from promptwise.handlers.detection import _handle_emit_siem

_SCTX = typing.cast(ServerContext, None)


def test_emit_siem_tool_file_drop(tmp_path):
    out = json.loads(asyncio.run(_handle_emit_siem(_SCTX, {
        "record": _finding(), "mode": "file", "drop_dir": str(tmp_path / "siem")})))
    assert out["written"] is True
