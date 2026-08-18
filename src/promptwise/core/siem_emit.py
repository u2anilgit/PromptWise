"""siem_emit -- map detection findings / audit records to OCSF class dicts
(primary export shape) and CEF lines (legacy SIEM ingest), then either
drop them to a local JSONL file (default) or forward via the existing
WebhookSink. No vendor SDKs -- dict mapping + json/str formatting only,
stdlib.

OCSF field names loosely follow the OWASP Agentic Operations Security
(AOS) trace-extension guidance where applicable (actor/user shape,
class_uid convention) -- this is this project's own mapping, not a
generated client for any OCSF schema registry.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from promptwise.core.audit_sinks import WebhookSink

# OCSF "Detection Finding" class family (class_uid 2004xx range is the
# real OCSF Findings category; using a project-local placeholder uid
# namespaced clearly as non-canonical until validated against a live OCSF
# schema registry is out of scope for this WP -- documented here, not
# silently presented as an official mapping).
_OCSF_CLASS_UID = 200401
_OCSF_CATEGORY_UID = 2  # Findings


def _severity_id(threat_score: float) -> int:
    # OCSF severity_id: 1=Informational .. 6=Fatal (5=Critical). Map our
    # 0-100 threat_score onto that scale, monotonic.
    if threat_score >= 90:
        return 6
    if threat_score >= 70:
        return 5
    if threat_score >= 50:
        return 4
    if threat_score >= 25:
        return 3
    if threat_score > 0:
        return 2
    return 1


def to_ocsf(record: dict) -> dict:
    threat_score = float(record.get("threat_score", 0.0))
    return {
        "class_uid": _OCSF_CLASS_UID,
        "category_uid": _OCSF_CATEGORY_UID,
        "activity_id": 1,  # Create
        "severity_id": _severity_id(threat_score),
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": {"user": {"name": record.get("actor", "")}},
        "message": record.get("detail", ""),
        "unmapped": {
            "category": record.get("category", ""),
            "threat_score": threat_score,
            "aivss_breakdown": record.get("aivss_breakdown", {}),
            "evidence": record.get("evidence", {}),
        },
    }


def _cef_escape_header(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|")


def _cef_escape_extension(value: str) -> str:
    return value.replace("\\", "\\\\").replace("=", "\\=")


def to_cef(record: dict) -> str:
    threat_score = float(record.get("threat_score", 0.0))
    severity = _severity_id(threat_score)
    name = _cef_escape_header(record.get("category", "anomaly"))
    detail = _cef_escape_extension(record.get("detail", ""))
    actor = _cef_escape_extension(record.get("actor", ""))
    score_str = str(threat_score) if threat_score != int(threat_score) else str(int(threat_score))
    return (
        f"CEF:0|PromptWise|BehaviorAnomalyDetector|1.0|{name}|{name}|{severity}|"
        f"suser={actor} msg={detail} threatScore={score_str}"
    )


class SiemEmitter:
    def __init__(self, mode: str = "file", drop_dir: str | Path = ".promptwise/siem/", webhook_url: str | None = None):
        self.mode = mode if mode in ("file", "webhook") else "file"
        self.drop_dir = Path(drop_dir)
        self.webhook_url = webhook_url

    def emit(self, record: dict) -> dict:
        event = to_ocsf(record)
        if self.mode == "webhook" and self.webhook_url:
            sink = WebhookSink(self.webhook_url)
            ok = sink.send(event)
            return {"mode": "webhook", "sent": ok}

        self.drop_dir.mkdir(parents=True, exist_ok=True)
        date_tag = time.strftime("%Y%m%d", time.gmtime())
        filename = f"siem-{date_tag}.jsonl"
        path = self.drop_dir / filename
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
        return {"mode": "file", "written": True, "path": filename}
