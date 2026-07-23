"""dashboard.auth -- role-based access control for the dashboard's Flask
app (the only network-reachable surface in this codebase; the MCP tool
layer has no inbound listener and is intentionally out of scope).

Credentials are never stored in plaintext: an operator generates a raw
value out-of-band (e.g. via the stdlib `secrets` module), the value is
hashed here, and only the hash lives in config/dashboard_auth.yaml. This
module never persists a raw value anywhere.

`Identity.projects` exists so per-project data scoping has a place to
live once it's wired to real data (cost_logs has no project_id column
today -- see the design doc); it is not enforced by anything yet.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Identity:
    credential_id: str  # first 12 hex chars of the credential hash -- stable, non-reversible, safe to log as an audit actor
    role: str  # "viewer" or "admin"
    projects: list[str] | None = None  # None = unrestricted; not enforced anywhere yet


_ROLE_RANK = {"viewer": 0, "admin": 1}


def hash_credential(raw: str) -> str:
    """One-way sha256 hex digest. The only form a credential ever takes
    once it leaves the operator's hands -- never compared or stored as
    plaintext past this call."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_credentials(path: Path | str) -> list[dict]:
    """Parse config/dashboard_auth.yaml's `entries` list. Missing file or
    any parse error yields an empty list -- fail-closed for auth (an
    empty credential list means no request from a non-loopback bind can
    ever succeed, which is the safe failure direction here, unlike the
    fail-open convention this codebase uses for optional features)."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        entries = data.get("entries", [])
        return [e for e in entries if isinstance(e, dict) and e.get("credential_hash")]
    except Exception:
        return []


def find_identity(raw_credential: str, credentials: list[dict]) -> Identity | None:
    """Look up the Identity for a raw (unhashed) credential presented on a
    request, against the loaded credential entries. None when there's no
    match -- caller must treat that as unauthenticated."""
    target = hash_credential(raw_credential)
    for entry in credentials:
        if entry.get("credential_hash") == target:
            role = entry.get("role", "viewer")
            if role not in _ROLE_RANK:
                role = "viewer"
            return Identity(credential_id=target[:12], role=role, projects=entry.get("projects"))
    return None


def role_satisfies(role: str, minimum: str) -> bool:
    """True when `role` grants at least `minimum` access (admin satisfies
    a viewer requirement; viewer does not satisfy an admin requirement)."""
    return _ROLE_RANK.get(role, -1) >= _ROLE_RANK.get(minimum, 0)