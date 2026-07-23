"""Task 9 (P1) — SIEM-streamable audit export (webhook/syslog sink).

The hash-chained JSONL file stays the default and the source of truth
(unchanged if no sink is configured -- opt-in only). A configured sink is a
best-effort side channel: any failure there must never raise out of
AuditLog.append() or break the chain.
"""
import json
import socket

import pytest

from promptwise.core.audit_log import AuditLog
from promptwise.core.audit_sinks import WebhookSink, SyslogSink, load_sinks_from_config


# ── WebhookSink ──────────────────────────────────────────────────────────────
def test_webhook_sink_posts_json_and_returns_true_on_success(monkeypatch):
    posted = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"{}"

    def _fake_urlopen(req, timeout=None):
        posted["url"] = req.full_url
        posted["data"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    sink = WebhookSink(url="https://siem.example.com/ingest")
    ok = sink.send({"task": "rewrite_prompt", "cost_usd": 0.01})
    assert ok is True
    assert posted["url"] == "https://siem.example.com/ingest"
    assert posted["data"]["task"] == "rewrite_prompt"


def test_webhook_sink_returns_false_never_raises_on_network_failure(monkeypatch):
    import urllib.request

    def _boom(req, timeout=None):
        raise OSError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    sink = WebhookSink(url="https://siem.example.com/ingest")
    assert sink.send({"task": "x"}) is False


# ── SyslogSink ───────────────────────────────────────────────────────────────
def test_syslog_sink_sends_udp_datagram_with_json_payload(monkeypatch):
    sent = {}

    class _FakeSocket:
        def __init__(self, *a, **k): pass
        def sendto(self, data, addr):
            sent["data"] = data
            sent["addr"] = addr
        def close(self): pass

    monkeypatch.setattr(socket, "socket", lambda *a, **k: _FakeSocket())

    sink = SyslogSink(host="siem.local", port=514)
    ok = sink.send({"task": "rewrite_prompt"})
    assert ok is True
    assert sent["addr"] == ("siem.local", 514)
    body = sent["data"].decode("utf-8")
    assert "rewrite_prompt" in body


def test_syslog_sink_returns_false_never_raises_on_socket_failure(monkeypatch):
    def _boom(*a, **k):
        raise OSError("network unreachable")
    monkeypatch.setattr(socket, "socket", _boom)

    sink = SyslogSink(host="siem.local", port=514)
    assert sink.send({"task": "x"}) is False


# ── AuditLog integration ─────────────────────────────────────────────────────
def test_audit_log_with_no_sinks_behaves_exactly_as_before(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    rec = log.append(task="t1")
    assert rec.task == "t1"
    assert len(log.records) == 1


def test_audit_log_forwards_to_configured_sink_on_append(tmp_path):
    calls = []

    class _Recording:
        def send(self, record):
            calls.append(record)
            return True

    log = AuditLog(tmp_path / "audit.jsonl", sinks=[_Recording()])
    log.append(task="t1")
    assert len(calls) == 1
    assert calls[0]["task"] == "t1"


def test_audit_log_sink_failure_never_breaks_append_or_the_chain(tmp_path):
    class _Broken:
        def send(self, record):
            raise RuntimeError("siem is down")

    log = AuditLog(tmp_path / "audit.jsonl", sinks=[_Broken()])
    rec = log.append(task="t1")  # must not raise
    assert rec.task == "t1"
    ok, msg = log.verify()
    assert ok
    # File export remains the source of truth even when the sink is broken.
    assert (tmp_path / "audit.jsonl").exists()


def test_audit_log_forwards_to_multiple_sinks(tmp_path):
    calls_a, calls_b = [], []

    class _A:
        def send(self, record): calls_a.append(record); return True

    class _B:
        def send(self, record): calls_b.append(record); return True

    log = AuditLog(tmp_path / "audit.jsonl", sinks=[_A(), _B()])
    log.append(task="t1")
    assert len(calls_a) == 1 and len(calls_b) == 1


# ── config-driven sink loading (opt-in) ─────────────────────────────────────
def test_load_sinks_from_config_builds_webhook_and_syslog_sinks(tmp_path):
    cfg = tmp_path / "audit_sinks.yaml"
    cfg.write_text(
        "sinks:\n"
        "  - type: webhook\n"
        "    url: https://siem.example.com/ingest\n"
        "  - type: syslog\n"
        "    host: siem.local\n"
        "    port: 514\n",
        encoding="utf-8",
    )
    sinks = load_sinks_from_config(cfg)
    assert len(sinks) == 2
    assert isinstance(sinks[0], WebhookSink)
    assert isinstance(sinks[1], SyslogSink)


def test_load_sinks_from_config_missing_file_returns_empty_list(tmp_path):
    assert load_sinks_from_config(tmp_path / "nope.yaml") == []


def test_load_sinks_from_config_unknown_type_is_skipped_not_fatal(tmp_path):
    cfg = tmp_path / "audit_sinks.yaml"
    cfg.write_text("sinks:\n  - type: carrier_pigeon\n", encoding="utf-8")
    assert load_sinks_from_config(cfg) == []
