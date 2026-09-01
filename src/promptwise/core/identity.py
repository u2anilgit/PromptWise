"""core.identity -- three-tier, fail-open identity resolution.

Session-scoped (see core/session_context.py's CURRENT_SESSION_ID docstring
for the same one-process-per-session convention): resolve_identity() is
called once per MCP server process and the result cached on ServerContext.

Tiers, each falling open to the next on any failure -- this NEVER raises
and NEVER blocks a tool call:
  1. LDAP bind via the configured domain controller (config.identity.ldap_server)
     -> sAMAccountName, memberOf groups, mail. Skipped entirely when
     ldap_server is unset, when the optional `ldap3` extras group isn't
     installed, or on any bind/search error.
  2. USERDOMAIN/USERDNSDOMAIN/USERNAME (Windows) or USER (POSIX) env vars
     -> domain + username, no group data.
  3. Anonymous -- today's behavior, empty username, matches every prior
     free-text/hardcoded actor call site.

See docs/superpowers/specs/2026-08-31-promptwise-enterprise-identity-phase1-design.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # only present if the `ldap` extras group is installed
    from ldap3 import Connection, Server, SUBTREE  # type: ignore
    LDAP3_AVAILABLE = True
except Exception:
    Connection = None  # type: ignore
    Server = None  # type: ignore
    SUBTREE = None  # type: ignore
    LDAP3_AVAILABLE = False


@dataclass(frozen=True)
class Identity:
    username: str = ""
    domain: str = ""
    groups: list[str] = field(default_factory=list)
    email: str = ""
    source: str = "anonymous"  # "ldap" | "env" | "anonymous"


def _cn_from_dn(dn: str) -> str:
    """'CN=PromptWise-Admins,OU=Groups,DC=corp,DC=local' -> 'PromptWise-Admins'."""
    first = dn.split(",", 1)[0]
    return first.split("=", 1)[1] if "=" in first else first


def _resolve_tier1_ldap(config) -> "Identity | None":
    if not LDAP3_AVAILABLE or not config or not config.ldap_server:
        return None
    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if not username:
        return None
    try:
        server = Server(config.ldap_server)
        with Connection(server, authentication="SASL", sasl_mechanism="GSSAPI") as conn:
            conn.search(
                config.ldap_search_base or "",
                f"(sAMAccountName={username})",
                SUBTREE,
                attributes=["sAMAccountName", "mail", "memberOf"],
            )
            if not conn.entries:
                return None
            entry = conn.entries[0]
            groups = [_cn_from_dn(dn) for dn in list(getattr(entry, "memberOf", []) or [])]
            resolved_username = list(getattr(entry, "sAMAccountName", []) or [username])[0]
            emails = list(getattr(entry, "mail", []) or [])
            domain = os.environ.get("USERDOMAIN", "")
            return Identity(username=resolved_username, domain=domain, groups=groups,
                             email=emails[0] if emails else "", source="ldap")
    except Exception:
        return None


def _resolve_tier2_env() -> "Identity | None":
    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if not username:
        return None
    domain = os.environ.get("USERDOMAIN") or os.environ.get("USERDNSDOMAIN") or ""
    return Identity(username=username, domain=domain, groups=[], email="", source="env")


def resolve_identity(config=None) -> Identity:
    """Tiered, fail-open identity resolution. Never raises."""
    try:
        ldap_identity = _resolve_tier1_ldap(config)
        if ldap_identity is not None:
            return ldap_identity
    except Exception:
        pass
    try:
        env_identity = _resolve_tier2_env()
        if env_identity is not None:
            return env_identity
    except Exception:
        pass
    return Identity()


def resolved_actor(explicit: str, identity: "Identity | None" = None, remote_identity=None) -> str:
    """Caller-supplied `actor` wins (service-account/automation contexts);
    otherwise the resolved AD Identity's username; otherwise a remote
    MCP transport's credential_id (see transports/http_server.py --
    duck-typed here via getattr, not imported by name, to avoid
    core/ depending on dashboard/); otherwise "" (today's behavior,
    unchanged when nothing resolves)."""
    if explicit:
        return explicit
    if identity is not None and identity.username:
        return identity.username
    return getattr(remote_identity, "credential_id", "") if remote_identity is not None else ""
