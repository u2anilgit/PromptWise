"""dashboard.oidc_auth -- OIDC login for the dashboard (Authlib-based).

Supplements, never replaces, dashboard/auth.py's static-credential Bearer
path. All secrets (issuer, client_id, client_secret, redirect_uri) and the
session-cookie signing key come from environment variables, never a
committed config file -- config/oidc_roles.yaml holds only non-secret
claim-name/role-name mapping, the same discipline
docs/OPS_REMOTE_MCP.md's PROMPTWISE_DB_URL fix established.

Role mapping here is SAFE in a way Phase 1's (removed) AD-group dashboard
RBAC was not: map_role_from_claims operates on THIS request's own
verified, signed ID-token claims (Authlib validates the signature via the
IdP's JWKS before these claims are ever seen here), not a process-wide OS
lookup unrelated to who actually sent the HTTP request.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from promptwise.dashboard.auth import _ROLE_RANK


@dataclass(frozen=True)
class OIDCConfig:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    group_claim: str = "groups"

    @classmethod
    def from_env(cls) -> "OIDCConfig | None":
        """None when OIDC is not configured -- PROMPTWISE_OIDC_ISSUER unset
        means the feature is simply off, dashboard behaves exactly as
        before this plan."""
        issuer = os.environ.get("PROMPTWISE_OIDC_ISSUER", "")
        if not issuer:
            return None
        return cls(
            issuer=issuer,
            client_id=os.environ.get("PROMPTWISE_OIDC_CLIENT_ID", ""),
            client_secret=os.environ.get("PROMPTWISE_OIDC_CLIENT_SECRET", ""),
            redirect_uri=os.environ.get("PROMPTWISE_OIDC_REDIRECT_URI", ""),
            group_claim=os.environ.get("PROMPTWISE_OIDC_GROUP_CLAIM", "groups"),
        )


def map_role_from_claims(claims: dict, group_claim: str, group_role_map: dict[str, str]) -> str:
    """Highest-ranked role granted by any group in claims[group_claim].
    Defaults to "viewer" (least privilege) when the claim is missing or no
    group matches -- mirrors find_identity's existing default-role
    behavior in dashboard/auth.py.

    Defensive against malformed IdP claim shapes: if claims[group_claim]
    is not a list (e.g. an int, dict, or string) it is treated as no
    groups matched rather than raised; non-hashable/unmatchable entries
    within a list are skipped individually rather than crashing the whole
    lookup. This function must never raise on attacker- or
    misconfiguration-controlled claim content -- a malformed claim shape
    is a "viewer" role, never a 500."""
    groups = claims.get(group_claim) if isinstance(claims, dict) else None
    if not isinstance(groups, list):
        groups = []
    matched = []
    for g in groups:
        try:
            if g in group_role_map:
                matched.append(group_role_map[g])
        except TypeError:
            # unhashable entry (e.g. a dict/list group value) -- skip it
            continue
    if not matched:
        return "viewer"
    return max(matched, key=lambda role: _ROLE_RANK.get(role, -1))


def load_group_role_map(path) -> dict[str, str]:
    """Parse config/oidc_roles.yaml's `group_role_map` mapping. Missing
    file, parse error, or an unrecognized role value yields {} / drops
    that entry -- same fail-closed-for-auth posture as
    dashboard/auth.py's load_ad_group_map."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        raw = data.get("group_role_map", {}) or {}
        return {str(k): str(v) for k, v in raw.items() if str(v) in _ROLE_RANK}
    except Exception:
        return {}


def build_oauth_client(app, config: OIDCConfig):
    """Register the OIDC client on `app` via Authlib's Flask integration.
    Authlib handles discovery, PKCE, and ID-token signature verification
    against the IdP's JWKS internally -- no custom crypto in this module."""
    from authlib.integrations.flask_client import OAuth

    oauth = OAuth(app)
    return oauth.register(
        name="oidc",
        server_metadata_url=f"{config.issuer.rstrip('/')}/.well-known/openid-configuration",
        client_id=config.client_id,
        client_secret=config.client_secret,
        client_kwargs={"scope": "openid email profile"},
    )
