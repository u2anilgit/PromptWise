"""WP3 -- export_incident_bundle: reuses compliance_export.py's exact
Ed25519 sign + zip pipeline (no new envelope format), adding three
regulatory-regime sections (NIS2 24h early-warning, GDPR 72h Art.33, EU AI
Act Art.73 serious-incident fields). Anti-fabrication discipline matches
security/framework_map.py: a field is populated ONLY when the incident
record genuinely carries the underlying data -- never guessed.
"""
import asyncio
import json
import typing

from promptwise.core.audit_log import AuditLog
from promptwise.core.incidents import IncidentStore
from promptwise.core.tool_registry import ServerContext

import promptwise.server  # noqa: F401 -- collection-order guard, see WP1 Task 6 / WP2 Tasks 3/5/7/9
from promptwise.handlers.incidents import _handle_export_incident_bundle

_BCTX = typing.cast(ServerContext, None)


def test_export_incident_bundle_signs_and_verifies(tmp_path, monkeypatch):
    from promptwise.core.compliance_export import ENV_KEY_ED25519, generate_ed25519_keypair
    monkeypatch.setenv(ENV_KEY_ED25519, generate_ed25519_keypair()["private_key"])
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr(
        "promptwise.handlers.incidents._get_audit_log",
        lambda: AuditLog(tmp_path / "audit.jsonl"))

    store = IncidentStore(tmp_path / "wp3.db")
    inc = store.create("Test incident", severity="high")
    audit = AuditLog(tmp_path / "audit.jsonl")
    audit.append("anomaly_detected", actor="alice", rules_applied=["novel_tool_sequence"])

    out = json.loads(asyncio.run(_handle_export_incident_bundle(_BCTX, {
        "incident_id": inc.id, "correlation_key": "novel_tool_sequence"})))

    assert "bundle" in out and "signature" in out
    from promptwise.core.compliance_export import verify_bundle
    verification = verify_bundle(out)
    assert verification.ok


def test_export_incident_bundle_has_three_regulatory_sections(tmp_path, monkeypatch):
    from promptwise.core.compliance_export import ENV_KEY_ED25519, generate_ed25519_keypair
    monkeypatch.setenv(ENV_KEY_ED25519, generate_ed25519_keypair()["private_key"])
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr(
        "promptwise.handlers.incidents._get_audit_log",
        lambda: AuditLog(tmp_path / "audit.jsonl"))
    store = IncidentStore(tmp_path / "wp3.db")
    inc = store.create("Test incident", severity="high")

    out = json.loads(asyncio.run(_handle_export_incident_bundle(_BCTX, {
        "incident_id": inc.id, "correlation_key": "x"})))
    manifest = out["bundle"]["manifest"]
    assert "nis2" in manifest and "gdpr" in manifest and "eu_ai_act" in manifest


def test_export_incident_bundle_omits_unavailable_fields_never_guesses(tmp_path, monkeypatch):
    from promptwise.core.compliance_export import ENV_KEY_ED25519, generate_ed25519_keypair
    monkeypatch.setenv(ENV_KEY_ED25519, generate_ed25519_keypair()["private_key"])
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr(
        "promptwise.handlers.incidents._get_audit_log",
        lambda: AuditLog(tmp_path / "audit.jsonl"))
    store = IncidentStore(tmp_path / "wp3.db")
    inc = store.create("Bare incident")  # no severity, no description, no events

    out = json.loads(asyncio.run(_handle_export_incident_bundle(_BCTX, {
        "incident_id": inc.id, "correlation_key": "x"})))
    gdpr = out["bundle"]["manifest"]["gdpr"]
    # fields with no underlying data are OMITTED from the dict, not present
    # with a placeholder/guessed value
    assert all(v not in (None, "unknown", "TBD", "") for v in gdpr.values())


def test_export_incident_bundle_unknown_incident_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    out = json.loads(asyncio.run(_handle_export_incident_bundle(_BCTX, {
        "incident_id": 999, "correlation_key": "x"})))
    assert "error" in out


def test_export_incident_bundle_no_key_configured_returns_clean_error(tmp_path, monkeypatch):
    """E2E smoke-test finding: on a fresh install with no Ed25519 key
    configured, the handler must return a clean {"error", "type": "KeyError"}
    JSON object instead of raising an uncaught KeyError."""
    from promptwise.core.compliance_export import ENV_KEY_ED25519, ENV_KEY_FILE_ED25519
    monkeypatch.delenv(ENV_KEY_ED25519, raising=False)
    monkeypatch.delenv(ENV_KEY_FILE_ED25519, raising=False)
    monkeypatch.setattr("promptwise.core.incidents._default_db", lambda: tmp_path / "wp3.db")
    monkeypatch.setattr(
        "promptwise.handlers.incidents._get_audit_log",
        lambda: AuditLog(tmp_path / "audit.jsonl"))
    store = IncidentStore(tmp_path / "wp3.db")
    inc = store.create("Test incident", severity="high")

    out = json.loads(asyncio.run(_handle_export_incident_bundle(_BCTX, {
        "incident_id": inc.id, "correlation_key": "x"})))

    assert out["type"] == "KeyError"
    assert "error" in out and "Ed25519" in out["error"]
