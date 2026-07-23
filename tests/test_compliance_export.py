"""Compliance evidence export — self-verifying, signed bundle from the audit chain.

TDD for Phase 7 WP7.2. Stdlib only, air-gap safe: no network, no new dependency.
"""
import builtins
import json
import os

import pytest

from promptwise.core.audit_log import AuditLog
from promptwise.core import compliance_export as ce

KEY = "s3cr3t-local-audit-key"
WRONG = "not-the-key"


@pytest.fixture(autouse=True)
def _isolate_risk_register_db(tmp_path, monkeypatch):
    """build_bundle() now constructs a RiskRegister() internally, which
    resolves its db path via promptwise.db.models.get_db_path() -- this
    always points at the real ~/.promptwise/promptwise.db regardless of
    cwd, so every test in this file (all of which call build_bundle,
    directly or via sign_bundle/export_bundle) must have it patched to a
    tmp_path location to avoid writing test data into the real user db.
    """
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")


def _records():
    """A short, valid hash chain exported to plain dicts (as the JSONL holds them)."""
    log = AuditLog()
    log.append("draft story S1", agent="claude-code", model="sonnet",
               cost_usd=0.01, gate_decision="PASS", rules_applied=["security"])
    log.append("implement S1", agent="cursor", model="sonnet", cost_usd=0.02,
               gate_decision="CONCERNS", files_touched=["a.py"])
    log.append("review S1", agent="codex", gate_decision="PASS")
    return json.loads(log.export_json())


# ---------- chain verification ----------
def test_verify_chain_ok_on_untouched_data():
    res = ce.verify_chain(_records())
    assert res.ok, res.message
    assert res.first_broken_index is None


def test_verify_chain_accepts_auditlog_object():
    log = AuditLog()
    log.append("t0", agent="claude-code")
    res = ce.verify_chain(log)
    assert res.ok


@pytest.mark.parametrize("idx", [0, 1, 2])
def test_mutation_points_to_first_broken_record(idx):
    recs = _records()
    recs[idx]["task"] = "TAMPERED"
    res = ce.verify_chain(recs)
    assert not res.ok
    assert res.first_broken_index == idx
    assert res.first_broken_id == recs[idx]["hash"]


def test_first_broken_is_earliest_when_multiple_mutations():
    recs = _records()
    recs[2]["cost_usd"] = 9.99
    recs[1]["cost_usd"] = 5.55
    res = ce.verify_chain(recs)
    assert not res.ok
    assert res.first_broken_index == 1


# ---------- bundle build ----------
def test_build_bundle_manifest():
    recs = _records()
    bundle = ce.build_bundle(recs)
    m = bundle["manifest"]
    assert m["record_count"] == 3
    assert m["chain_verified"] is True
    assert m["chain_head"] == recs[-1]["hash"]
    assert m["time_range"]["start"] == recs[0]["timestamp"]
    assert m["time_range"]["end"] == recs[-1]["timestamp"]
    assert bundle["records"] == recs


def test_build_bundle_empty_chain():
    bundle = ce.build_bundle([])
    assert bundle["manifest"]["record_count"] == 0
    assert bundle["manifest"]["chain_verified"] is True


def test_control_family_tagging_is_generic():
    bundle = ce.build_bundle(_records(), control_families=["audit-and-accountability"])
    fams = bundle["manifest"]["control_families"]
    assert "audit-and-accountability" in fams
    # no branded / competitor framework names leak through
    blob = json.dumps(bundle).lower()
    for banned in ("soc2", "soc 2", "hipaa", "iso 27001", "nist", "pci"):
        assert banned not in blob


# ---------- signing ----------
def test_sign_and_verify_roundtrip_with_explicit_key():
    signed = ce.sign_bundle(ce.build_bundle(_records()), key=KEY)
    assert signed["signature"]["alg"] == "HMAC-SHA256"
    res = ce.verify_bundle(signed, key=KEY)
    assert res.ok
    assert res.signature_ok
    assert res.chain.ok


def test_verify_fails_with_wrong_key():
    signed = ce.sign_bundle(ce.build_bundle(_records()), key=KEY)
    res = ce.verify_bundle(signed, key=WRONG)
    assert not res.ok
    assert not res.signature_ok
    # chain itself is still intact even though signature is wrong
    assert res.chain.ok


def test_verify_fails_with_missing_key(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_AUDIT_KEY", raising=False)
    monkeypatch.delenv("PROMPTWISE_AUDIT_KEY_FILE", raising=False)
    signed = ce.sign_bundle(ce.build_bundle(_records()), key=KEY)
    res = ce.verify_bundle(signed)  # no key available anywhere
    assert not res.ok
    assert not res.signature_ok


def test_key_from_env_var(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_AUDIT_KEY", KEY)
    signed = ce.sign_bundle(ce.build_bundle(_records()))  # picks up env
    res = ce.verify_bundle(signed)  # also from env
    assert res.ok


def test_key_from_key_file(tmp_path, monkeypatch):
    monkeypatch.delenv("PROMPTWISE_AUDIT_KEY", raising=False)
    kf = tmp_path / "audit.key"
    kf.write_text(KEY, encoding="utf-8")
    monkeypatch.setenv("PROMPTWISE_AUDIT_KEY_FILE", str(kf))
    signed = ce.sign_bundle(ce.build_bundle(_records()))
    assert ce.verify_bundle(signed).ok


def test_tamper_inside_signed_bundle_fails_and_locates():
    signed = ce.sign_bundle(ce.build_bundle(_records()), key=KEY)
    signed["bundle"]["records"][1]["task"] = "HACKED"
    res = ce.verify_bundle(signed, key=KEY)
    assert not res.ok
    assert res.chain.first_broken_index == 1
    assert not res.signature_ok  # signature also breaks under mutation


# ---------- zip packaging (stdlib zipfile) ----------
def test_zip_roundtrip(tmp_path):
    signed = ce.sign_bundle(ce.build_bundle(_records()), key=KEY)
    out = tmp_path / "evidence.zip"
    ce.write_zip(signed, out)
    assert out.exists()
    loaded = ce.read_zip(out)
    res = ce.verify_bundle(loaded, key=KEY)
    assert res.ok


# ---------- offline / air-gap ----------
def test_no_network_used(monkeypatch):
    import socket

    def _boom(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    signed = ce.sign_bundle(ce.build_bundle(_records()), key=KEY)
    assert ce.verify_bundle(signed, key=KEY).ok


# ---------- Ed25519 keygen + key resolution ----------
def test_generate_ed25519_keypair_returns_hex_pair():
    pair = ce.generate_ed25519_keypair()
    assert set(pair) == {"private_key", "public_key"}
    assert len(bytes.fromhex(pair["private_key"])) == 32
    assert len(bytes.fromhex(pair["public_key"])) == 32


def test_generate_ed25519_keypair_is_random():
    a = ce.generate_ed25519_keypair()
    b = ce.generate_ed25519_keypair()
    assert a["private_key"] != b["private_key"]


def test_resolve_ed25519_key_from_explicit_arg():
    pair = ce.generate_ed25519_keypair()
    priv = ce._resolve_ed25519_key(pair["private_key"])
    assert priv.public_key().public_bytes_raw().hex() == pair["public_key"]


def test_resolve_ed25519_key_from_env_var(monkeypatch):
    pair = ce.generate_ed25519_keypair()
    monkeypatch.setenv(ce.ENV_KEY_ED25519, pair["private_key"])
    priv = ce._resolve_ed25519_key()
    assert priv.public_key().public_bytes_raw().hex() == pair["public_key"]


def test_resolve_ed25519_key_from_key_file(tmp_path, monkeypatch):
    pair = ce.generate_ed25519_keypair()
    keyfile = tmp_path / "ed25519.key"
    keyfile.write_text(pair["private_key"])
    monkeypatch.delenv(ce.ENV_KEY_ED25519, raising=False)
    monkeypatch.setenv(ce.ENV_KEY_FILE_ED25519, str(keyfile))
    priv = ce._resolve_ed25519_key()
    assert priv.public_key().public_bytes_raw().hex() == pair["public_key"]


def test_resolve_ed25519_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv(ce.ENV_KEY_ED25519, raising=False)
    monkeypatch.delenv(ce.ENV_KEY_FILE_ED25519, raising=False)
    with pytest.raises(KeyError):
        ce._resolve_ed25519_key()


# ---------- Ed25519 sign/verify ----------
def test_ed25519_sign_and_verify_roundtrip():
    pair = ce.generate_ed25519_keypair()
    signed = ce.sign_bundle_ed25519(ce.build_bundle(_records()), key=pair["private_key"])
    assert signed["signature"]["alg"] == "Ed25519"
    assert signed["signature"]["public_key"] == pair["public_key"]
    res = ce.verify_bundle(signed)  # no key arg needed — pubkey is embedded
    assert res.ok
    assert res.signature_ok
    assert res.chain.ok


def test_ed25519_verify_fails_on_tampered_bundle():
    pair = ce.generate_ed25519_keypair()
    signed = ce.sign_bundle_ed25519(ce.build_bundle(_records()), key=pair["private_key"])
    signed["bundle"]["records"][0]["task"] = "TAMPERED"
    res = ce.verify_bundle(signed)
    assert not res.signature_ok


def test_ed25519_verify_fails_on_tampered_signature():
    pair = ce.generate_ed25519_keypair()
    signed = ce.sign_bundle_ed25519(ce.build_bundle(_records()), key=pair["private_key"])
    signed["signature"]["value"] = "00" * 64
    res = ce.verify_bundle(signed)
    assert not res.signature_ok


def test_ed25519_chain_tamper_detected_independent_of_signature():
    pair = ce.generate_ed25519_keypair()
    bundle = ce.build_bundle(_records())
    bundle["records"][1]["task"] = "TAMPERED"
    signed = ce.sign_bundle_ed25519(bundle, key=pair["private_key"])
    res = ce.verify_bundle(signed)
    assert res.signature_ok  # signature matches the (already-tampered) bundle bytes
    assert not res.chain.ok  # but the chain re-walk still catches it
    assert not res.ok


def test_verify_bundle_dispatches_on_alg_hmac_unaffected():
    signed = ce.sign_bundle(ce.build_bundle(_records()), key=KEY)
    assert signed["signature"]["alg"] == ce.SIG_ALG
    res = ce.verify_bundle(signed, key=KEY)
    assert res.ok


# ---------- export_bundle(sign_alg=...) ----------
def test_export_bundle_ed25519_end_to_end(tmp_path, monkeypatch):
    pair = ce.generate_ed25519_keypair()
    monkeypatch.setenv(ce.ENV_KEY_ED25519, pair["private_key"])
    summary = ce.export_bundle(_records(), sign_alg="ed25519", out_path=tmp_path / "bundle.zip")
    assert summary["signed"] is True
    assert summary["signature"]["alg"] == "Ed25519"
    assert summary["verified"]["ok"] is True
    loaded = ce.read_zip(tmp_path / "bundle.zip")
    assert ce.verify_bundle(loaded).ok


def test_export_bundle_ed25519_fails_open_without_key(monkeypatch):
    monkeypatch.delenv(ce.ENV_KEY_ED25519, raising=False)
    monkeypatch.delenv(ce.ENV_KEY_FILE_ED25519, raising=False)
    summary = ce.export_bundle(_records(), sign_alg="ed25519")
    assert summary["signed"] is False
    assert "sign_error" in summary


def test_export_bundle_default_sign_alg_is_hmac(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_AUDIT_KEY", KEY)
    summary = ce.export_bundle(_records())
    assert summary["signature"]["alg"] == ce.SIG_ALG


def test_export_bundle_ed25519_fails_open_on_malformed_env_key_non_hex(monkeypatch):
    monkeypatch.delenv(ce.ENV_KEY_FILE_ED25519, raising=False)
    monkeypatch.setenv(ce.ENV_KEY_ED25519, "not-valid-hex")
    summary = ce.export_bundle(_records(), sign_alg="ed25519")
    assert summary["signed"] is False
    assert "sign_error" in summary


def test_export_bundle_ed25519_fails_open_on_malformed_env_key_wrong_length(monkeypatch):
    monkeypatch.delenv(ce.ENV_KEY_FILE_ED25519, raising=False)
    monkeypatch.setenv(ce.ENV_KEY_ED25519, "aa" * 16)  # valid hex, but only 16 bytes not 32
    summary = ce.export_bundle(_records(), sign_alg="ed25519")
    assert summary["signed"] is False
    assert "sign_error" in summary


def test_resolve_ed25519_key_from_env_var_strips_whitespace(monkeypatch):
    pair = ce.generate_ed25519_keypair()
    monkeypatch.setenv(ce.ENV_KEY_ED25519, pair["private_key"] + "\n")
    priv = ce._resolve_ed25519_key()
    assert priv.public_key().public_bytes_raw().hex() == pair["public_key"]


# ---------- verify_bundle: unknown alg falls through to HMAC branch ----------
def test_verify_bundle_unknown_alg_falls_through_to_hmac_branch(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_AUDIT_KEY", raising=False)
    monkeypatch.delenv("PROMPTWISE_AUDIT_KEY_FILE", raising=False)
    signed = ce.sign_bundle(ce.build_bundle(_records()), key=KEY)
    signed["signature"]["alg"] = "RSA-4096"
    # no valid HMAC key/signature match available -> should not raise, just fail closed
    res = ce.verify_bundle(signed)
    assert res.signature_ok is False
    assert res.ok is False


# ---------- residual risk register integration ----------
def test_build_bundle_manifest_includes_residual_risk_summary(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")
    bundle = ce.build_bundle(_records())
    assert "residual_risk_summary" in bundle["manifest"]
    assert set(bundle["manifest"]["residual_risk_summary"]) == {"open", "accepted", "expired"}


def test_build_bundle_residual_risk_summary_reflects_register_state(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")
    from promptwise.security.risk_register import RiskRegister
    RiskRegister().upsert("secrets", "some_pattern")
    bundle = ce.build_bundle(_records())
    assert bundle["manifest"]["residual_risk_summary"]["open"] == 1
