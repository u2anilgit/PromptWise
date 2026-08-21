import time

from promptwise.core.audit_log import AuditLog
from promptwise.core.fleet import FleetRegistry, build_fleet_report


def _registry(tmp_path):
    return FleetRegistry(db_path=tmp_path / "fleet.db")


def test_report_includes_every_registered_agent(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="reviewer", allowed_tools=["Read"])
    reg.register("agent-b", role="writer", allowed_tools=["Write"])
    report = build_fleet_report(reg, audit_log=AuditLog(path=tmp_path / "audit.jsonl"), cost_logs=[])
    ids = {a["agent_id"] for a in report["agents"]}
    assert ids == {"agent-a", "agent-b"}
    assert report["generated_at"]


def test_report_attributes_cost_by_tool_overlap(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="reviewer", allowed_tools=["Read", "Grep"])
    cost_logs = [
        {"tool": "Read", "cost_usd": 0.10}, {"tool": "Grep", "cost_usd": 0.05},
        {"tool": "Bash", "cost_usd": 5.00},  # not in agent-a's scope -- excluded
    ]
    report = build_fleet_report(reg, audit_log=AuditLog(path=tmp_path / "audit.jsonl"), cost_logs=cost_logs)
    agent_a = next(a for a in report["agents"] if a["agent_id"] == "agent-a")
    assert round(agent_a["estimated_cost_usd"], 2) == 0.15


def test_report_computes_gate_pass_rate(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="reviewer", allowed_tools=["Read"])
    log = AuditLog(path=tmp_path / "audit.jsonl")
    log.append("t1", actor="agent-a", gate_decision="PASS")
    log.append("t2", actor="agent-a", gate_decision="PASS")
    log.append("t3", actor="agent-a", gate_decision="FAIL")
    report = build_fleet_report(reg, audit_log=log, cost_logs=[])
    agent_a = next(a for a in report["agents"] if a["agent_id"] == "agent-a")
    assert round(agent_a["gate_pass_rate"], 4) == round(2 / 3, 4)


def test_report_gate_pass_rate_none_when_no_gated_records(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="reviewer", allowed_tools=["Read"])
    report = build_fleet_report(reg, audit_log=AuditLog(path=tmp_path / "audit.jsonl"), cost_logs=[])
    agent_a = next(a for a in report["agents"] if a["agent_id"] == "agent-a")
    assert agent_a["gate_pass_rate"] is None


def test_report_flags_stale_credential(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="deployer", allowed_tools=["Bash"],
                  scoped_credential=True, last_rotation_date="2020-01-01")
    reg.register("agent-b", role="deployer2", allowed_tools=["Bash"],
                  scoped_credential=True, last_rotation_date=time.strftime("%Y-%m-%d"))
    reg.register("agent-c", role="unscoped", allowed_tools=["Bash"], scoped_credential=False)
    report = build_fleet_report(reg, audit_log=AuditLog(path=tmp_path / "audit.jsonl"), cost_logs=[])
    flags = {a["agent_id"]: a["stale_credential"] for a in report["agents"]}
    assert flags == {"agent-a": True, "agent-b": False, "agent-c": False}


def test_report_uses_last_known_drift_score(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="reviewer", allowed_tools=["Read"])
    reg.update_drift("agent-a", 42.0, "2026-08-21T00:00:00Z")
    report = build_fleet_report(reg, audit_log=AuditLog(path=tmp_path / "audit.jsonl"), cost_logs=[])
    agent_a = next(a for a in report["agents"] if a["agent_id"] == "agent-a")
    assert agent_a["drift_score"] == 42.0
