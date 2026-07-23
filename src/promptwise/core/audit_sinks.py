"""audit_sinks — optional, opt-in SIEM-streamable sinks for the audit trail
(P1 Task 9).

The hash-chained JSONL file (``AuditLog``'s ``path``) stays the default sink
and the source of truth, exactly as before this task. A sink here is a
best-effort side channel a caller explicitly configures (``AuditLog(...,
sinks=[...])``); any sink failure is swallowed and never raises out of
``AuditLog.append()`` or breaks the hash chain -- see the fail-soft contract
enforced in ``AuditLog._forward_to_sinks``.

Stdlib only: ``WebhookSink`` uses ``urllib.request`` (already the pattern in
``scanner.py``'s OSV lookup); ``SyslogSink`` sends a UDP datagram via the
stdlib ``socket`` module rather than depending on a SIEM client library.
"""
from __future__ import annotations

import json
import socket
import urllib.request
from pathlib import Path

try:  # PyYAML is already a PromptWise dependency (policy/model registry/governor use it)
    import yaml
except Exception:  # pragma: no cover - yaml always present in practice
    yaml = None  # type: ignore


class WebhookSink:
    """POST each audit record as JSON to a webhook URL (Splunk HEC / generic
    SIEM ingest endpoint / any HTTP collector). Never raises: ``send``
    returns ``True``/``False``."""

    def __init__(self, url: str, timeout: float = 2.0, headers: dict | None = None):
        self.url = url
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json", **(headers or {})}

    def send(self, record: dict) -> bool:
        try:
            req = urllib.request.Request(
                self.url, data=json.dumps(record).encode("utf-8"),
                headers=self.headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout):
                pass
            return True
        except Exception:
            return False


class SyslogSink:
    """Forward each audit record as a JSON-payload UDP syslog datagram
    (RFC 5424-ish priority prefix; body is JSON rather than free text so a
    SIEM can parse it structurally). Never raises: ``send`` returns
    ``True``/``False``."""

    # facility=local0 (16), severity=informational (6) -> priority 134.
    _DEFAULT_PRIORITY = 134

    def __init__(self, host: str, port: int = 514, priority: int = _DEFAULT_PRIORITY):
        self.host = host
        self.port = port
        self.priority = priority

    def send(self, record: dict) -> bool:
        try:
            body = f"<{self.priority}>{json.dumps(record)}".encode("utf-8")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.sendto(body, (self.host, self.port))
            finally:
                sock.close()
            return True
        except Exception:
            return False


def load_sinks_from_config(path: str | Path) -> list:
    """Build sinks from an optional YAML config (``sinks: [{type: webhook|
    syslog, ...}]``). Fail-soft by design: a missing file, unparseable YAML,
    or an unrecognized ``type`` yields an empty/partial list rather than
    raising -- this is an opt-in convenience loader, not a required one, and
    the process must start fine with no sinks configured at all."""
    p = Path(path)
    if not p.exists() or yaml is None:
        return []
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    sinks = []
    for entry in (data.get("sinks") or []):
        if not isinstance(entry, dict):
            continue
        kind = entry.get("type")
        try:
            if kind == "webhook" and entry.get("url"):
                sinks.append(WebhookSink(url=entry["url"], timeout=float(entry.get("timeout", 2.0))))
            elif kind == "syslog" and entry.get("host"):
                sinks.append(SyslogSink(host=entry["host"], port=int(entry.get("port", 514))))
            # Unknown types are silently skipped -- see docstring.
        except Exception:
            continue
    return sinks
