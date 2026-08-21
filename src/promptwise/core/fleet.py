"""core.fleet -- agent fleet governance (WP5). A persistent registry of the
AI agents operating against this repo: role, responsibilities, allowed
tools, budget, owner, and OWASP NHI Top 10 credential metadata (scoped-
credential flag, last-rotation date, JIT-grant linkage by signature).

Raw-sqlite via get_db_path() (~/.promptwise/promptwise.db), same file every
other security/governance store in this codebase uses -- matches
core/jit_permissions.py / security/threat_intel.py's pattern exactly. No
new pip dependency.
"""
from __future__ import annotations

import json
import sqlite3
import time
from itertools import combinations
from pathlib import Path


def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class FleetRegistry:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else _default_db()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS agent_registry (
                       agent_id             TEXT PRIMARY KEY,
                       role                 TEXT NOT NULL DEFAULT '',
                       responsibilities_json TEXT NOT NULL DEFAULT '[]',
                       allowed_tools_json   TEXT NOT NULL DEFAULT '[]',
                       budget_usd           REAL NOT NULL DEFAULT 0.0,
                       priority             TEXT NOT NULL DEFAULT 'medium',
                       owner                TEXT NOT NULL DEFAULT '',
                       scoped_credential    INTEGER NOT NULL DEFAULT 0,
                       last_rotation_date   TEXT NOT NULL DEFAULT '',
                       jit_grant_signature  TEXT NOT NULL DEFAULT '',
                       registered_at        TEXT NOT NULL,
                       updated_at           TEXT NOT NULL,
                       last_drift_score     REAL NOT NULL DEFAULT 0.0,
                       last_drift_checked_at TEXT NOT NULL DEFAULT ''
                   )""")
            conn.commit()
        finally:
            conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        return {
            "agent_id": row["agent_id"], "role": row["role"],
            "responsibilities": json.loads(row["responsibilities_json"]),
            "allowed_tools": json.loads(row["allowed_tools_json"]),
            "budget_usd": row["budget_usd"], "priority": row["priority"],
            "owner": row["owner"], "scoped_credential": bool(row["scoped_credential"]),
            "last_rotation_date": row["last_rotation_date"],
            "jit_grant_signature": row["jit_grant_signature"],
            "registered_at": row["registered_at"], "updated_at": row["updated_at"],
            "last_drift_score": row["last_drift_score"],
            "last_drift_checked_at": row["last_drift_checked_at"],
        }

    def register(
        self, agent_id: str, *, role: str = "", responsibilities: list[str] | None = None,
        allowed_tools: list[str] | None = None, budget_usd: float = 0.0, priority: str = "medium",
        owner: str = "", scoped_credential: bool = False, last_rotation_date: str = "",
        jit_grant_signature: str = "",
    ) -> dict:
        ts = _now()
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT registered_at FROM agent_registry WHERE agent_id = ?", (agent_id,)).fetchone()
            registered_at = existing["registered_at"] if existing else ts
            conn.execute(
                "INSERT INTO agent_registry (agent_id, role, responsibilities_json, allowed_tools_json, "
                "budget_usd, priority, owner, scoped_credential, last_rotation_date, jit_grant_signature, "
                "registered_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(agent_id) DO UPDATE SET role=excluded.role, "
                "responsibilities_json=excluded.responsibilities_json, "
                "allowed_tools_json=excluded.allowed_tools_json, budget_usd=excluded.budget_usd, "
                "priority=excluded.priority, owner=excluded.owner, "
                "scoped_credential=excluded.scoped_credential, "
                "last_rotation_date=excluded.last_rotation_date, "
                "jit_grant_signature=excluded.jit_grant_signature, updated_at=excluded.updated_at",
                (agent_id, role, json.dumps(responsibilities or []), json.dumps(allowed_tools or []),
                 float(budget_usd), priority, owner, int(bool(scoped_credential)), last_rotation_date,
                 jit_grant_signature, registered_at, ts))
            conn.commit()
            row = conn.execute("SELECT * FROM agent_registry WHERE agent_id = ?", (agent_id,)).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row)

    def get(self, agent_id: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM agent_registry WHERE agent_id = ?", (agent_id,)).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row) if row else None

    def list_all(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM agent_registry ORDER BY agent_id").fetchall()
        finally:
            conn.close()
        return [self._row_to_dict(r) for r in rows]

    def update_drift(self, agent_id: str, score: float, checked_at: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE agent_registry SET last_drift_score = ?, last_drift_checked_at = ? "
                "WHERE agent_id = ?", (float(score), checked_at, agent_id))
            conn.commit()
        finally:
            conn.close()

    def delete(self, agent_id: str) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM agent_registry WHERE agent_id = ?", (agent_id,))
            conn.commit()
        finally:
            conn.close()


def detect_sprawl(registry: "FleetRegistry", *, jaccard_threshold: float = 0.6) -> dict:
    """Capability-overlap report across registered agents: tool-set Jaccard
    similarity for every pair above `jaccard_threshold`, plus role
    duplication (2+ agents sharing a non-empty role string). Pure
    read-only comparison over FleetRegistry.list_all() -- no side effects."""
    agents = registry.list_all()
    pairs: list[dict] = []
    for a, b in combinations(agents, 2):
        set_a, set_b = set(a["allowed_tools"]), set(b["allowed_tools"])
        union = set_a | set_b
        if not union:
            continue
        jaccard = len(set_a & set_b) / len(union)
        if jaccard >= jaccard_threshold:
            pairs.append({
                "agent_a": a["agent_id"], "agent_b": b["agent_id"], "jaccard": round(jaccard, 4),
                "shared_tools": sorted(set_a & set_b),
            })
    pairs.sort(key=lambda p: (-p["jaccard"], p["agent_a"], p["agent_b"]))

    role_map: dict[str, list[str]] = {}
    for a in agents:
        if a["role"]:
            role_map.setdefault(a["role"], []).append(a["agent_id"])
    role_duplicates = {role: sorted(ids) for role, ids in role_map.items() if len(ids) >= 2}

    return {"pairs": pairs, "role_duplicates": role_duplicates}


def detect_agent_drift(
    registry: "FleetRegistry", agent_id: str, *, audit_log=None, window_days: int = 7,
    drift_threshold: float = 60.0, auto_incident: bool = True, incident_store=None,
) -> dict:
    """Compare an agent's recent audit-trail activity against its
    registered role/allowed_tools by reusing WP2's baseline machinery
    verbatim: two BehaviorStats snapshots (one synthesized from the
    registered scope, one built from observed rules_applied/files_touched)
    handed to anomaly_detector.detect_anomalies(). A finding whose
    threat_score crosses `drift_threshold` auto-creates a WP3 incident,
    fail-soft -- mirrors handlers/incidents.py's WP4 correlate_threats
    hook exactly: a broken/missing incident store must never raise out of
    this function."""
    from promptwise.core.anomaly_detector import detect_anomalies
    from promptwise.core.audit_log import AuditLog
    from promptwise.core.behavior_baseline import BehaviorStats

    agent = registry.get(agent_id)
    if agent is None:
        return {"error": f"no registered agent '{agent_id}'", "type": "UnknownAgent"}

    log = audit_log if audit_log is not None else AuditLog()
    records = log.query(actor=agent_id)

    allowed = agent["allowed_tools"] or []
    baseline_bigrams = {f"{a}->{b}": 1 for a in allowed for b in allowed}
    baseline = BehaviorStats(actor=agent_id, window_days=window_days, tool_bigram_freq=baseline_bigrams)

    observed_bigrams: dict[str, int] = {}
    files: set[str] = set()
    for rec in records:
        actions = rec.get("rules_applied", []) or []
        for a, b in zip(actions, actions[1:]):
            key = f"{a}->{b}"
            observed_bigrams[key] = observed_bigrams.get(key, 0) + 1
        files.update(rec.get("files_touched", []) or [])
    window = BehaviorStats(
        actor=agent_id, window_days=window_days, tool_bigram_freq=observed_bigrams,
        distinct_files_touched=len(files))

    findings = detect_anomalies(agent_id, window=window, baseline=baseline)
    drift_score = max((f.threat_score for f in findings), default=0.0)

    now = _now()
    registry.update_drift(agent_id, drift_score, now)

    incident_created = False
    incident_id = None
    if auto_incident and findings and drift_score >= drift_threshold:
        try:
            from promptwise.core.incidents import IncidentStore
            categories = ", ".join(sorted({f.category for f in findings}))
            store = incident_store if incident_store is not None else IncidentStore()
            inc = store.create(
                title=f"agent drift: {agent_id}",
                description=f"detect_agent_drift flagged {categories} for registered agent "
                             f"'{agent_id}' (role={agent['role']!r}, drift_score={drift_score:.1f})",
                severity="high" if drift_score >= 80 else "medium",
                metadata={"agent_id": agent_id, "drift_score": drift_score,
                          "categories": sorted({f.category for f in findings})})
            incident_created = True
            incident_id = inc.id
        except Exception:
            pass

    return {
        "agent_id": agent_id, "findings": [f.to_dict() for f in findings],
        "drift_score": drift_score, "incident_created": incident_created, "incident_id": incident_id,
    }
