# tests/test_identity.py
from promptwise.config import IdentityConfig
from promptwise.core.identity import Identity, resolve_identity, resolved_actor


def test_tier3_anonymous_fallback_when_no_config_and_no_env(monkeypatch):
    monkeypatch.delenv("USERDOMAIN", raising=False)
    monkeypatch.delenv("USERDNSDOMAIN", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.delenv("USER", raising=False)
    identity = resolve_identity(IdentityConfig())
    assert identity.source == "anonymous"
    assert identity.username == ""
    assert identity.groups == []


def test_tier2_env_fallback_when_ldap_server_not_configured(monkeypatch):
    monkeypatch.setenv("USERDOMAIN", "CORP")
    monkeypatch.setenv("USERNAME", "jdoe")
    monkeypatch.delenv("USER", raising=False)
    identity = resolve_identity(IdentityConfig())  # ldap_server="" -> tier 1 skipped
    assert identity.source == "env"
    assert identity.username == "jdoe"
    assert identity.domain == "CORP"
    assert identity.groups == []


def test_tier2_env_fallback_uses_unix_user_var(monkeypatch):
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.setenv("USER", "jdoe")
    monkeypatch.delenv("USERDOMAIN", raising=False)
    identity = resolve_identity(IdentityConfig())
    assert identity.source == "env"
    assert identity.username == "jdoe"
    assert identity.domain == ""


def test_tier1_ldap_bind_success(monkeypatch):
    class _FakeEntry:
        sAMAccountName = ["jdoe"]
        mail = ["jdoe@corp.local"]
        memberOf = ["CN=PromptWise-Admins,OU=Groups,DC=corp,DC=local"]

    class _FakeConnection:
        entries = [_FakeEntry()]

        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def search(self, *a, **kw):
            return True

    import promptwise.core.identity as identity_mod
    monkeypatch.setattr(identity_mod, "LDAP3_AVAILABLE", True)
    monkeypatch.setattr(identity_mod, "Connection", _FakeConnection)
    monkeypatch.setattr(identity_mod, "Server", lambda *a, **kw: object())
    monkeypatch.setattr(identity_mod, "SUBTREE", "SUBTREE")
    monkeypatch.setenv("USERNAME", "jdoe")
    monkeypatch.setenv("USERDOMAIN", "CORP")

    identity = resolve_identity(IdentityConfig(ldap_server="ldaps://dc.corp.local", ldap_search_base="dc=corp,dc=local"))
    assert identity.source == "ldap"
    assert identity.username == "jdoe"
    assert identity.email == "jdoe@corp.local"
    assert identity.groups == ["PromptWise-Admins"]


def test_tier1_ldap_bind_failure_falls_open_to_tier2(monkeypatch):
    import promptwise.core.identity as identity_mod

    class _RaisingConnection:
        def __init__(self, *a, **kw):
            raise OSError("no DC reachable")

    monkeypatch.setattr(identity_mod, "LDAP3_AVAILABLE", True)
    monkeypatch.setattr(identity_mod, "Connection", _RaisingConnection)
    monkeypatch.setattr(identity_mod, "Server", lambda *a, **kw: object())
    monkeypatch.setenv("USERNAME", "jdoe")
    monkeypatch.setenv("USERDOMAIN", "CORP")

    identity = resolve_identity(IdentityConfig(ldap_server="ldaps://dc.corp.local"))
    assert identity.source == "env"
    assert identity.username == "jdoe"


def test_ldap3_not_installed_falls_open_to_tier2(monkeypatch):
    import promptwise.core.identity as identity_mod
    monkeypatch.setattr(identity_mod, "LDAP3_AVAILABLE", False)
    monkeypatch.setenv("USERNAME", "jdoe")
    monkeypatch.delenv("USERDOMAIN", raising=False)

    identity = resolve_identity(IdentityConfig(ldap_server="ldaps://dc.corp.local"))
    assert identity.source == "env"


def test_resolved_actor_prefers_explicit_caller_value():
    identity = Identity(username="jdoe", domain="CORP", groups=[], email="", source="env")
    assert resolved_actor("service-account-x", identity) == "service-account-x"


def test_resolved_actor_falls_back_to_identity_username():
    identity = Identity(username="jdoe", domain="CORP", groups=[], email="", source="env")
    assert resolved_actor("", identity) == "jdoe"


def test_resolved_actor_empty_when_no_identity_and_no_explicit():
    assert resolved_actor("", None) == ""
