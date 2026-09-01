"""dashboard.auth -- role-based access control for the dashboard's Flask
app. Its hash_credential/load_credentials/find_identity functions are
also reused by transports/http_server.py for the optional remote MCP
transport's token auth (see config/mcp_auth.yaml) -- same mechanism,
separate credentials file, since dashboard viewer/admin roles are a
different access shape than MCP tool-call access.

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
    # Bearer-token path: first 12 hex chars of the credential hash -- stable,
    # non-reversible, safe to log as an audit actor. OIDC session path
    # (dashboard/web.py): an IdP-namespaced identifier ("oidc:<sub>", or a
    # hash-based placeholder when the IdP omits `sub`) -- still stable and
    # safe to log as an actor, but not guaranteed non-reversible the way the
    # Bearer-token hash is.
    credential_id: str
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


# NOTE: currently unwired. Phase 1 final review found process-identity-based
# remote dashboard auth unsafe -- it would grant a role based on the AD
# groups of the OS user running the dashboard process, not the actual HTTP
# requester, with no way to authenticate a specific request. Kept here for a
# future Phase 2 effort that wires this to per-request SSO (e.g. Kerberos/
# SPNEGO) instead of the process identity.
def resolve_role_from_groups(groups: list[str], ad_group_map: dict[str, str]) -> str | None:
    """Highest-ranked role granted by any of `groups`' AD-group mapping.
    None when no group matches -- caller falls back to the static
    credential-file path (this never widens access beyond the static file
    on its own)."""
    matched = [ad_group_map[g] for g in groups if g in ad_group_map]
    if not matched:
        return None
    return max(matched, key=lambda role: _ROLE_RANK.get(role, -1))


def load_ad_group_map(path) -> dict[str, str]:
    """Parse config/dashboard_auth.yaml's `ad_groups` mapping. Same
    fail-closed posture as load_credentials -- missing file, parse error,
    or an unrecognized role value yields {} / drops that entry."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        raw = data.get("ad_groups", {}) or {}
        return {str(k): str(v) for k, v in raw.items() if str(v) in _ROLE_RANK}
    except Exception:
        return {}