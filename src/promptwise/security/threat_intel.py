"""security.threat_intel -- STIX 2.1 minimal-subset parser and storage
(WP4). No `stix2` pip dependency (ground rule #3): this module only ever
reads the handful of fields PromptWise's correlation logic actually uses
from `indicator`/`attack-pattern`/`intrusion-set`/`relationship` objects.
Any other STIX object `type` (`malware`, `campaign`, ...) is skipped, not
errored -- fail-soft, matches the project's detector-failure discipline.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

_SUPPORTED_TYPES = {
    "indicator": "indicators",
    "attack-pattern": "attack_patterns",
    "intrusion-set": "intrusion_sets",
    "relationship": "relationships",
}

_REQUIRED_FIELDS = {
    "indicator": ("id", "pattern"),
    "attack-pattern": ("id", "name"),
    "intrusion-set": ("id", "name"),
    "relationship": ("id", "source_ref", "target_ref", "relationship_type"),
}


def parse_bundle(bundle: dict) -> dict:
    """Parse a STIX 2.1 bundle dict into the four supported object-type
    buckets. Anything malformed or of an unsupported type is skipped, never
    raised -- a partially-bad feed still yields whatever is usable."""
    result: dict = {v: [] for v in _SUPPORTED_TYPES.values()}
    if not isinstance(bundle, dict) or bundle.get("type") != "bundle":
        return result
    for obj in bundle.get("objects", []) or []:
        if not isinstance(obj, dict):
            continue
        obj_type = obj.get("type")
        bucket = _SUPPORTED_TYPES.get(obj_type)
        if bucket is None:
            continue
        required = _REQUIRED_FIELDS[obj_type]
        if not all(obj.get(f) for f in required):
            continue
        result[bucket].append(obj)
    return result


def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


def _atlas_technique_id(obj: dict) -> str:
    for ref in obj.get("external_references", []) or []:
        if isinstance(ref, dict) and ref.get("source_name") == "mitre-atlas":
            return ref.get("external_id", "") or ""
    return ""


_TYPE_LABEL = {
    "indicators": "indicator", "attack_patterns": "attack-pattern",
    "intrusion_sets": "intrusion-set", "relationships": "relationship",
}


class ThreatIntelStore:
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
                """CREATE TABLE IF NOT EXISTS intel_objects (
                       id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                       stix_id             TEXT NOT NULL UNIQUE,
                       type                TEXT NOT NULL,
                       name                TEXT,
                       pattern             TEXT,
                       atlas_technique_id  TEXT,
                       source              TEXT NOT NULL,
                       imported_at         TEXT NOT NULL,
                       raw_json            TEXT NOT NULL
                   )""")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS intel_matches (
                       id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                       intel_object_id     INTEGER NOT NULL,
                       audit_record_id     TEXT,
                       incident_id         INTEGER,
                       matched_on          TEXT NOT NULL,
                       created_at          TEXT NOT NULL
                   )""")
            # audit_record_id/incident_id are nullable (a match is tagged
            # with only one of the two), and SQLite treats NULL as distinct
            # from NULL for UNIQUE purposes -- COALESCE the nullable columns
            # to sentinel values so two matches that both leave the same
            # column NULL are still recognized as duplicates.
            conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS idx_intel_matches_unique
                   ON intel_matches (intel_object_id, COALESCE(audit_record_id, ''),
                                      COALESCE(incident_id, -1), matched_on)""")
            conn.commit()
        finally:
            conn.close()

    def upsert_objects(self, parsed: dict, source: str) -> int:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        count = 0
        conn = self._connect()
        try:
            for bucket, objs in parsed.items():
                obj_type = _TYPE_LABEL.get(bucket, bucket)
                for obj in objs:
                    stix_id = obj.get("id", "")
                    if not stix_id:
                        continue
                    existing = conn.execute(
                        "SELECT id FROM intel_objects WHERE stix_id = ?", (stix_id,)).fetchone()
                    if existing:
                        conn.execute(
                            "UPDATE intel_objects SET name=?, pattern=?, atlas_technique_id=?, "
                            "source=?, imported_at=?, raw_json=? WHERE stix_id=?",
                            (obj.get("name", ""), obj.get("pattern", ""), _atlas_technique_id(obj),
                             source, ts, json.dumps(obj), stix_id))
                    else:
                        conn.execute(
                            "INSERT INTO intel_objects "
                            "(stix_id, type, name, pattern, atlas_technique_id, source, imported_at, raw_json) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (stix_id, obj_type, obj.get("name", ""), obj.get("pattern", ""),
                             _atlas_technique_id(obj), source, ts, json.dumps(obj)))
                    count += 1
            conn.commit()
        finally:
            conn.close()
        return count

    def get_by_stix_id(self, stix_id: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM intel_objects WHERE stix_id = ?", (stix_id,)).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def list_objects(self, obj_type: str | None = None) -> list[dict]:
        conn = self._connect()
        try:
            if obj_type:
                rows = conn.execute(
                    "SELECT * FROM intel_objects WHERE type = ? ORDER BY imported_at DESC", (obj_type,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM intel_objects ORDER BY imported_at DESC").fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]


def import_bundle_file(bundle_path: str, source: str, store: "ThreatIntelStore | None" = None) -> dict:
    path = Path(bundle_path)
    bundle = json.loads(path.read_text(encoding="utf-8"))  # raises FileNotFoundError/JSONDecodeError unchanged
    parsed = parse_bundle(bundle)
    store = store or ThreatIntelStore()
    imported = store.upsert_objects(parsed, source=source)
    return {"imported": imported, "source": source}


def correlate(
    store: ThreatIntelStore, *, content: str = "",
    atlas_technique_ids: list[str] | None = None,
    audit_record_id: str = "", incident_id: int = 0,
) -> list[dict]:
    """Join a piece of content and/or a list of ATLAS technique IDs against
    stored intel. Returns an empty list on no match; callers that must not
    fail (e.g. the create_incident hook) should wrap this call themselves --
    this function can still raise on a sqlite error, it does not guarantee
    fail-soft on its own. Persists an `intel_matches` row per match only
    when the caller actually has something to tag (an audit record or an
    incident) -- a dry correlation probe with neither doesn't write. Repeat
    calls with identical arguments are deduped via INSERT OR IGNORE against
    a unique index on (intel_object_id, audit_record_id, incident_id,
    matched_on) -- safe to call repeatedly for backfill."""
    matches: list[dict] = []
    atlas_ids = set(atlas_technique_ids or [])

    for obj in store.list_objects("attack-pattern"):
        if obj.get("atlas_technique_id") and obj["atlas_technique_id"] in atlas_ids:
            matches.append({
                "intel_object_id": obj["id"], "stix_id": obj["stix_id"],
                "name": obj.get("name", ""), "matched_on": "atlas_technique_id",
            })

    if content:
        content_lower = content.lower()
        for obj in store.list_objects("indicator"):
            pattern = obj.get("pattern") or ""
            if pattern and _pattern_matches(pattern, content_lower):
                matches.append({
                    "intel_object_id": obj["id"], "stix_id": obj["stix_id"],
                    "name": obj.get("name", ""), "matched_on": "indicator_pattern",
                })

    if matches and (audit_record_id or incident_id):
        # NOTE: audit_record_id is the audit record's `index` field at the
        # time of the match. AuditLog.compact() renumbers indices during
        # compaction, so a stored audit_record_id could point at the wrong
        # record after a compaction runs -- known limitation, not fixed here.
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = store._connect()
        try:
            for m in matches:
                conn.execute(
                    "INSERT OR IGNORE INTO intel_matches (intel_object_id, audit_record_id, incident_id, matched_on, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (m["intel_object_id"], audit_record_id or None, incident_id or None, m["matched_on"], ts))
            conn.commit()
        finally:
            conn.close()

    return matches


def _pattern_matches(pattern: str, content_lower: str) -> bool:
    """Match an indicator's STIX `pattern` field against lower-cased content.
    Real STIX 2.1 patterning syntax (e.g. `[domain-name:value =
    'evil.example.com']`) never appears verbatim in free text, so quoted
    literals are extracted and matched individually. Falls back to a plain
    substring check for bare-token patterns (e.g. the seed bundle's
    "shai-hulud") so existing behavior is unchanged for those."""
    quoted = re.findall(r"'([^']+)'", pattern)
    if quoted:
        return any(q.lower() in content_lower for q in quoted)
    return pattern.lower() in content_lower


def enrich_audit(store: ThreatIntelStore, audit_log, audit_record_id: str) -> dict:
    """Append a read-only enrichment annotation to the audit trail for the
    intel matches already recorded against `audit_record_id`. Never mutates
    an existing record -- the enrichment is itself a new AuditLog.append()
    call, same as every other append pattern in this codebase."""
    conn = store._connect()
    try:
        rows = conn.execute(
            "SELECT im.matched_on, io.stix_id, io.name FROM intel_matches im "
            "JOIN intel_objects io ON io.id = im.intel_object_id "
            "WHERE im.audit_record_id = ?", (audit_record_id,)).fetchall()
    finally:
        conn.close()

    matches = [{"matched_on": r["matched_on"], "stix_id": r["stix_id"], "name": r["name"]} for r in rows]
    if not matches:
        return {"audit_record_id": audit_record_id, "matches": [], "enriched": False}

    names = ", ".join(m["stix_id"] for m in matches)
    audit_log.append(
        f"threat-intel enrichment for record {audit_record_id}: matched {names}",
        actor="threat_intel", compliance_decision="intel_enrichment")
    return {"audit_record_id": audit_record_id, "matches": matches, "enriched": True}


def export_indicators(store: ThreatIntelStore, fmt: str = "json") -> str:
    if fmt != "json":
        raise ValueError(f"unsupported export format: {fmt!r} (only 'json' is supported)")
    from promptwise.security.scanner import SecurityScanner
    scanner = SecurityScanner()
    out = []
    for obj in store.list_objects("indicator"):
        _, pattern = scanner.detect_pii(obj.get("pattern") or "", redact=True)
        _, name = scanner.detect_pii(obj.get("name") or "", redact=True)
        out.append({
            "stix_id": obj["stix_id"], "name": name,
            "pattern": pattern, "source": obj.get("source", ""),
        })
    return json.dumps({"indicators": out})
