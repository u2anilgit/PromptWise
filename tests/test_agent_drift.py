import json
import time

from promptwise.core.audit_log import AuditLog
from promptwise.core.fleet import FleetRegistry, detect_agent_drift
from promptwise.core.incidents import IncidentStore


def _registry(tmp_path):
    return FleetRegistry(db_path=tmp_path / "fleet.db")


def test_unknown_agent_returns_error_object(tmp_path):
    reg = _registry(tmp_path)
    log = AuditLog(path=tmp_path / "audit.jsonl")
    result = detect_agent_drift(reg, "ghost", audit_log=log)
    assert result == {"error": "no registered agent 'ghost'", "type": "UnknownAgent"}


def test_no_activity_yields_zero_drift(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="reviewer", allowed_tools=["Read", "Grep"])
    log = AuditLog(path=tmp_path / "audit.jsonl")
    result = detect_agent_drift(reg, "agent-a", audit_log=log)
    assert result["findings"] == []
    assert result["drift_score"] == 0.0
    assert result["incident_created"] is False


def test_read_only_agent_that_starts_writing_creates_incident(tmp_path):
    """The scenario named in the WP5 spec: a registered read-only agent's
    audit trail shows write-shaped activity outside its registered tool
    scope -> a drift finding fires -> an incident is auto-created."""
    reg = _registry(tmp_path)
    reg.register("agent-a", role="read-only-reviewer", allowed_tools=["Read", "Grep"])

    log = AuditLog(path=tmp_path / "audit.jsonl")
    # baseline-shaped activity would only ever bigram within {Read, Grep};
    # this actor's real trail chains Read->Bash->Write repeatedly, which is
    # both novel relative to the registered scope and matches
    # anomaly_detector.SUSPICIOUS_BIGRAMS' Read->Bash entry.
    for _ in range(4):
        log.append("did work", agent="agent-a", rules_applied=["Read", "Bash", "Write"],
                    files_touched=["secret.env"])

    incidents = IncidentStore(db_path=tmp_path / "incidents.db")
    result = detect_agent_drift(
        reg, "agent-a", audit_log=log, drift_threshold=1.0,
        auto_incident=True, incident_store=incidents)

    assert result["findings"], "expected at least one drift finding"
    assert result["drift_score"] > 0.0
    assert result["incident_created"] is True
    assert result["incident_id"] is not None

    rec = reg.get("agent-a")
    assert rec["last_drift_score"] == result["drift_score"]
    assert rec["last_drift_checked_at"]


def test_drift_below_threshold_does_not_create_incident(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="reviewer", allowed_tools=["Read", "Grep"])
    log = AuditLog(path=tmp_path / "audit.jsonl")
    log.append("looked around", agent="agent-a", rules_applied=["Read", "Grep"])
    result = detect_agent_drift(reg, "agent-a", audit_log=log, drift_threshold=99999.0)
    assert result["incident_created"] is False
    assert result["incident_id"] is None


def test_auto_incident_false_never_creates_incident(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="read-only-reviewer", allowed_tools=["Read"])
    log = AuditLog(path=tmp_path / "audit.jsonl")
    for _ in range(4):
        log.append("did work", agent="agent-a", rules_applied=["Read", "Bash", "Write"])
    result = detect_agent_drift(reg, "agent-a", audit_log=log, drift_threshold=0.0, auto_incident=False)
    assert result["incident_created"] is False
    assert result["incident_id"] is None


def test_window_days_excludes_records_older_than_window(tmp_path):
    """Records that would trigger a drift finding if included must be
    excluded once they fall outside `window_days` -- detect_agent_drift
    must bound its audit-log query with `since=`, not scan full history."""
    reg = _registry(tmp_path)
    reg.register("agent-a", role="read-only-reviewer", allowed_tools=["Read", "Grep"])
    log = AuditLog(path=tmp_path / "audit.jsonl")
    for _ in range(4):
        log.append("did work", agent="agent-a", rules_applied=["Read", "Bash", "Write"],
                    files_touched=["secret.env"])

    # Back-date every appended record to well outside the 7-day window.
    old_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 30 * 86400))
    audit_path = tmp_path / "audit.jsonl"
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    rewritten = []
    for line in lines:
        rec = json.loads(line)
        rec["timestamp"] = old_ts
        rewritten.append(json.dumps(rec))
    audit_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    result = detect_agent_drift(reg, "agent-a", audit_log=log, window_days=7, drift_threshold=1.0)
    assert result["findings"] == []
    assert result["drift_score"] == 0.0
    assert result["incident_created"] is False
