"""compliance_export — a self-verifying, signed evidence bundle from the audit chain.

The local audit trail (see ``audit_log``) is a tamper-evident, hash-chained JSONL.
This module packages that chain into a portable evidence bundle an auditor can verify
offline: it re-walks the hash chain, wraps the records in a manifest (time range,
record count, chain-head digest), and signs the canonicalized bytes with a local HMAC
key. Verification re-checks both the signature and the chain, and on tamper reports the
FIRST broken record.

Local-first and air-gap safe: stdlib only (``hashlib``/``hmac``/``json``/``zipfile``),
no network, no third-party dependency. Control-family tags are intentionally generic
(no branded/competitor framework names).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

from promptwise.core.audit_log import GENESIS, AuditLog, AuditRecord

# Local HMAC key sources, in precedence order: explicit arg > env value > env keyfile.
ENV_KEY = "PROMPTWISE_AUDIT_KEY"
ENV_KEY_FILE = "PROMPTWISE_AUDIT_KEY_FILE"

ENV_KEY_ED25519 = "PROMPTWISE_ED25519_KEY"
ENV_KEY_FILE_ED25519 = "PROMPTWISE_ED25519_KEY_FILE"

BUNDLE_SCHEMA = "promptwise.compliance.bundle/v1"
SIG_ALG = "HMAC-SHA256"
SIG_ALG_ED25519 = "Ed25519"

# Bundle members when serialized to a stdlib .zip.
_ZIP_MEMBER = "bundle.json"


@dataclass
class ChainResult:
    """Outcome of re-walking the hash chain."""

    ok: bool
    message: str
    first_broken_index: int | None = None
    first_broken_id: str | None = None
    chain_head: str = GENESIS

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "message": self.message,
            "first_broken_index": self.first_broken_index,
            "first_broken_id": self.first_broken_id,
            "chain_head": self.chain_head,
        }


@dataclass
class BundleVerification:
    """Outcome of verifying a signed bundle: signature AND chain."""

    ok: bool
    signature_ok: bool
    chain: ChainResult

    @property
    def first_broken_index(self) -> int | None:
        return self.chain.first_broken_index

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "signature_ok": self.signature_ok,
            "chain": self.chain.to_dict(),
        }


# ── helpers ──────────────────────────────────────────────────────────────────
def _coerce_records(source) -> list[dict]:
    """Accept an AuditLog, a JSONL path, or a list of record dicts -> list[dict]."""
    if isinstance(source, AuditLog):
        return json.loads(source.export_json())
    if isinstance(source, (str, Path)):
        log = AuditLog(source)
        return json.loads(log.export_json())
    return [dict(r) for r in source]


def _canonical_bytes(obj) -> bytes:
    """Deterministic, ascii-safe serialization used for hashing and signing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _record_hash(rec: dict) -> str | None:
    """Recompute a record's hash the same way audit_log does; None if malformed."""
    try:
        return AuditRecord(**rec).compute_hash()
    except TypeError:
        # Unknown/extra or missing fields => cannot reconstruct => treat as tampered.
        return None


def _resolve_key(key=None) -> bytes:
    """Resolve the local HMAC key from an explicit arg, env var, or key file."""
    if key is not None:
        return key.encode("utf-8") if isinstance(key, str) else bytes(key)
    env_val = os.environ.get(ENV_KEY)
    if env_val:
        return env_val.encode("utf-8")
    key_file = os.environ.get(ENV_KEY_FILE)
    if key_file and os.path.exists(key_file):
        data = Path(key_file).read_bytes().strip()
        if data:
            return data
    raise KeyError(
        f"no HMAC key available: set {ENV_KEY} or {ENV_KEY_FILE}, or pass key="
    )


def generate_ed25519_keypair() -> dict:
    """Generate a fresh Ed25519 keypair in memory. Never written to disk."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return {
        "private_key": private_key.private_bytes_raw().hex(),
        "public_key": public_key.public_bytes_raw().hex(),
    }


def _resolve_ed25519_key(key=None) -> Ed25519PrivateKey:
    """Resolve the local Ed25519 private key from an explicit arg, env var, or key file."""
    if key is not None:
        raw = bytes.fromhex(key) if isinstance(key, str) else bytes(key)
        return Ed25519PrivateKey.from_private_bytes(raw)
    env_val = os.environ.get(ENV_KEY_ED25519)
    if env_val:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(env_val))
    key_file = os.environ.get(ENV_KEY_FILE_ED25519)
    if key_file and os.path.exists(key_file):
        data = Path(key_file).read_text().strip()
        if data:
            return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(data))
    raise KeyError(
        f"no Ed25519 key available: set {ENV_KEY_ED25519} or {ENV_KEY_FILE_ED25519}, or pass key="
    )


# ── chain verification ───────────────────────────────────────────────────────
def verify_chain(source) -> ChainResult:
    """Re-walk the hash chain; on tamper, report the FIRST broken record.

    Adapts ``AuditLog.verify`` but works on plain record dicts (as held in the
    bundle / JSONL) and surfaces the offending index and record id.
    """
    records = _coerce_records(source)
    prev: str = GENESIS
    for i, rec in enumerate(records):
        rid: str = str(rec.get("hash") or "")
        if rec.get("index") != i:
            return ChainResult(False, f"index mismatch at record {i}", i, rid, prev)
        if rec.get("prev_hash") != prev:
            return ChainResult(False, f"broken link at record {i}", i, rid, prev)
        if _record_hash(rec) != rid:
            return ChainResult(False, f"tampered content at record {i}", i, rid, prev)
        prev = rid
    return ChainResult(True, f"verified {len(records)} record(s)", None, None, prev)


# ── control-family tagging (generic; no branded framework names) ──────────────
def derive_control_families(records: list[dict]) -> list[str]:
    """Infer generic control-family tags from the recorded governance signals."""
    fams: set[str] = set()
    if records:
        fams.add("audit-and-accountability")
    for rec in records:
        if rec.get("gate_decision"):
            fams.add("change-management")
        if rec.get("compliance_decision"):
            fams.add("compliance-monitoring")
        rules = " ".join(rec.get("rules_applied", [])).lower()
        if any(w in rules for w in ("security", "secret", "pii", "owasp", "injection")):
            fams.add("risk-assessment")
        if rec.get("actor") or rec.get("agent"):
            fams.add("identification-and-authentication")
    return sorted(fams)


# ── bundle build ─────────────────────────────────────────────────────────────
def build_bundle(source, *, control_families=None) -> dict:
    """Verify the chain, then package records + a manifest into a bundle dict."""
    records = _coerce_records(source)
    chain = verify_chain(records)
    fams = list(control_families) if control_families is not None else derive_control_families(records)
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "record_count": len(records),
        "time_range": {
            "start": records[0]["timestamp"] if records else None,
            "end": records[-1]["timestamp"] if records else None,
        },
        "chain_head": records[-1]["hash"] if records else GENESIS,
        "chain_verified": chain.ok,
        "chain_message": chain.message,
        "first_broken_index": chain.first_broken_index,
        "control_families": sorted(fams),
    }
    return {"manifest": manifest, "records": records}


# ── signing / verification ───────────────────────────────────────────────────
def sign_bundle(bundle: dict, key=None) -> dict:
    """HMAC-sign the canonicalized bundle bytes with the local key."""
    key_bytes = _resolve_key(key)
    signature = hmac.new(key_bytes, _canonical_bytes(bundle), hashlib.sha256).hexdigest()
    return {"bundle": bundle, "signature": {"alg": SIG_ALG, "value": signature}}


def verify_bundle(signed: dict, key=None) -> BundleVerification:
    """Re-check the HMAC signature and re-walk the chain; both must pass."""
    bundle = signed.get("bundle", {})
    sig = (signed.get("signature") or {}).get("value")

    signature_ok = False
    try:
        key_bytes = _resolve_key(key)
        expected = hmac.new(key_bytes, _canonical_bytes(bundle), hashlib.sha256).hexdigest()
        signature_ok = bool(sig) and hmac.compare_digest(expected, sig)
    except (KeyError, ValueError):
        signature_ok = False

    chain = verify_chain(bundle.get("records", []))
    return BundleVerification(ok=signature_ok and chain.ok, signature_ok=signature_ok, chain=chain)


# ── zip packaging (stdlib zipfile) ───────────────────────────────────────────
def write_zip(signed: dict, path) -> Path:
    """Write a signed bundle to a single-member .zip evidence archive."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(signed, indent=2, sort_keys=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_ZIP_MEMBER, payload)
    return path


def read_zip(path) -> dict:
    """Read a signed bundle back from a .zip evidence archive."""
    with zipfile.ZipFile(Path(path), "r") as zf:
        return json.loads(zf.read(_ZIP_MEMBER).decode("utf-8"))


# ── convenience: build + sign + optional zip in one call (used by the server) ─
def export_bundle(source, *, key=None, sign=True, control_families=None, out_path=None) -> dict:
    """One-shot: build a bundle, optionally sign it, optionally write a .zip.

    Returns a JSON-serializable summary (manifest, verification status, and the signed
    envelope). Fail-open: if signing is requested but no key is configured, the summary
    reports ``signed=False`` with the reason rather than raising.
    """
    bundle = build_bundle(source, control_families=control_families)
    summary: dict = {
        "manifest": bundle["manifest"],
        "chain_ok": bundle["manifest"]["chain_verified"],
        "signed": False,
    }
    envelope: dict = {"bundle": bundle}
    if sign:
        try:
            envelope = sign_bundle(bundle, key=key)
            verification = verify_bundle(envelope, key=key)
            summary["signed"] = True
            summary["signature"] = envelope["signature"]
            summary["verified"] = verification.to_dict()
        except KeyError as exc:
            summary["sign_error"] = str(exc)
    if out_path:
        summary["zip_path"] = str(write_zip(envelope, out_path))
    return summary
