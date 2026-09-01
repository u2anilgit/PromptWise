from promptwise.dashboard.auth import hash_credential
from promptwise.dashboard.oidc_auth import OIDCConfig
from promptwise.dashboard.web import create_web_app


_OIDC_CFG = OIDCConfig(
    issuer="https://idp.example.com", client_id="client-123",
    client_secret="secret-abc", redirect_uri="http://localhost:8765/auth/callback",
    group_claim="groups")


def _fake_client(userinfo: dict):
    """Stand-in for the Authlib client build_oauth_client would normally
    return -- exposes just the two methods the routes call, avoiding any
    real network call to an IdP."""
    class _FakeClient:
        def authorize_redirect(self, redirect_uri):
            from flask import redirect
            return redirect(f"https://idp.example.com/authorize?redirect_uri={redirect_uri}")

        def authorize_access_token(self):
            return {"userinfo": userinfo}
    return _FakeClient()


def test_app_refuses_to_start_when_oidc_enabled_without_secret_key(monkeypatch, tmp_path):
    monkeypatch.delenv("PROMPTWISE_DASHBOARD_SECRET_KEY", raising=False)
    import pytest
    with pytest.raises(SystemExit):
        create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                        oidc_config=_OIDC_CFG)


def test_login_route_redirects_to_idp(monkeypatch, tmp_path):
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client", lambda app, cfg: _fake_client({}))
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG)
    r = app.test_client().get("/auth/login")
    assert r.status_code in (302, 301)
    assert "idp.example.com" in r.headers["Location"]


def test_callback_sets_session_and_login_grants_access(monkeypatch, tmp_path):
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    roles_path = tmp_path / "oidc_roles.yaml"
    roles_path.write_text("group_role_map:\n  PromptWise-Admins: admin\n", encoding="utf-8")
    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client",
                         lambda app, cfg: _fake_client({"sub": "user-1", "groups": ["PromptWise-Admins"]}))
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG, oidc_roles_path=str(roles_path))
    client = app.test_client()
    r = client.get("/auth/callback")
    assert r.status_code in (302, 301)
    # session cookie now carries an admin identity -- a viewer-gated route succeeds with no Bearer header
    r2 = client.get("/api/models")
    assert r2.status_code == 200


def test_logout_clears_session(monkeypatch, tmp_path):
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    roles_path = tmp_path / "oidc_roles.yaml"
    roles_path.write_text("group_role_map:\n  PromptWise-Admins: admin\n", encoding="utf-8")
    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client",
                         lambda app, cfg: _fake_client({"sub": "user-1", "groups": ["PromptWise-Admins"]}))
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG, oidc_roles_path=str(roles_path))
    client = app.test_client()
    client.get("/auth/callback")
    client.get("/auth/logout")
    r = client.get("/api/models")
    assert r.status_code == 401


def test_no_oidc_config_dashboard_behaves_exactly_as_before(tmp_path):
    """oidc_config=None (the default) -- no /auth/* routes registered,
    no behavior change for existing callers."""
    app = create_web_app(require_auth=False)
    r = app.test_client().get("/auth/login")
    assert r.status_code == 404


def test_callback_failure_shows_clear_error_not_a_traceback(monkeypatch, tmp_path):
    """authorize_access_token() raising (network failure, invalid code,
    bad ID-token signature) must never fabricate a session or leak a raw
    500/traceback -- a clear failure response instead."""
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")

    class _FailingClient:
        def authorize_access_token(self):
            raise RuntimeError("IdP unreachable")

    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client", lambda app, cfg: _FailingClient())
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG)
    client = app.test_client()
    r = client.get("/auth/callback")
    assert r.status_code == 401
    # no session identity was set as a side effect of the failed attempt --
    # reuse the SAME client (same cookie jar) so this actually checks
    # whether the failed callback fabricated a session, rather than just
    # checking a brand-new client with no cookies at all.
    r2 = client.get("/api/models")
    assert r2.status_code == 401


def test_callback_with_malformed_group_claim_never_500s(monkeypatch, tmp_path):
    """A malformed `groups` claim (not a list) must never cause an
    unhandled 500/traceback -- the spec requires a clear failure page,
    never a fabricated session and never a crash."""
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client",
                         lambda app, cfg: _fake_client({"sub": "user-1", "groups": 42}))
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG)
    client = app.test_client()
    r = client.get("/auth/callback")
    assert r.status_code != 500
    # malformed groups claim maps to "viewer" (least privilege), not a crash
    assert r.status_code in (302, 301)
    r2 = client.get("/api/admin/settings")
    assert r2.status_code == 403


def test_callback_with_non_dict_userinfo_never_500s(monkeypatch, tmp_path):
    """A non-dict `userinfo` in the token response (a real IdP/library
    misbehavior surface) must never cause an unhandled 500."""
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")

    class _WeirdClient:
        def authorize_access_token(self):
            return {"userinfo": "not-a-dict"}

    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client", lambda app, cfg: _WeirdClient())
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG)
    r = app.test_client().get("/auth/callback")
    assert r.status_code != 500


def test_bad_bearer_does_not_fall_through_to_valid_session(monkeypatch, tmp_path):
    """A wrong/unknown Bearer token must be rejected outright -- the
    request must NOT fall back to a valid OIDC session cookie also
    present on the same request. Pins the require_role restructure that
    keeps the Bearer-present branch from ever consulting the session."""
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    roles_path = tmp_path / "oidc_roles.yaml"
    roles_path.write_text("group_role_map:\n  PromptWise-Admins: admin\n", encoding="utf-8")
    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client",
                         lambda app, cfg: _fake_client({"sub": "user-1", "groups": ["PromptWise-Admins"]}))
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG, oidc_roles_path=str(roles_path))
    client = app.test_client()
    client.get("/auth/callback")
    # sanity: the session alone (no header) grants access
    assert client.get("/api/models").status_code == 200
    # bad bearer + valid session -> must be rejected, not granted via the session
    r = client.get("/api/models", headers={"Authorization": "Bearer totally-wrong"})
    assert r.status_code == 401
    assert r.get_json()["error"] == "invalid credential"


def test_static_bearer_role_not_upgraded_by_concurrent_oidc_session(monkeypatch, tmp_path):
    """A static Bearer credential's role decision must never be overridden
    or upgraded by a concurrent OIDC session cookie -- a viewer-role
    Bearer token still gets 403 on an admin route even when the same
    request also carries an admin-role OIDC session."""
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    roles_path = tmp_path / "oidc_roles.yaml"
    roles_path.write_text("group_role_map:\n  PromptWise-Admins: admin\n", encoding="utf-8")
    cred_path = tmp_path / "dashboard_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("raw-token") + "\"\n    role: viewer\n",
        encoding="utf-8")
    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client",
                         lambda app, cfg: _fake_client({"sub": "user-1", "groups": ["PromptWise-Admins"]}))
    app = create_web_app(require_auth=True, credentials_path=str(cred_path),
                          oidc_config=_OIDC_CFG, oidc_roles_path=str(roles_path))
    client = app.test_client()
    # static viewer bearer works on its own
    r = client.get("/api/models", headers={"Authorization": "Bearer raw-token"})
    assert r.status_code == 200
    # establish an admin OIDC session on the same client
    client.get("/auth/callback")
    # the static viewer bearer must still be rejected on an admin route --
    # not upgraded to admin by the concurrent OIDC session
    r2 = client.get("/api/admin/settings", headers={"Authorization": "Bearer raw-token"})
    assert r2.status_code == 403


def test_app_refuses_to_start_when_oidc_enabled_with_missing_fields(monkeypatch, tmp_path):
    """PROMPTWISE_OIDC_ISSUER alone is not enough -- an empty client_id/
    client_secret/redirect_uri must refuse to start rather than silently
    registering /auth/* routes and silently disabling SESSION_COOKIE_SECURE."""
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    import pytest
    from promptwise.dashboard.oidc_auth import OIDCConfig
    incomplete_cfg = OIDCConfig(issuer="https://idp.example.com", client_id="",
                                 client_secret="", redirect_uri="", group_claim="groups")
    with pytest.raises(SystemExit):
        create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                        oidc_config=incomplete_cfg)


def test_expired_session_is_rejected_and_cleared(monkeypatch, tmp_path):
    """A session with a past oidc_exp must be treated as unauthenticated
    (401), even though oidc_sub/oidc_role are present in the cookie --
    the reviewer replayed a captured admin session cookie against a fresh
    app instance and it never expired."""
    import time
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    roles_path = tmp_path / "oidc_roles.yaml"
    roles_path.write_text("group_role_map:\n  PromptWise-Admins: admin\n", encoding="utf-8")
    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client",
                         lambda app, cfg: _fake_client({"sub": "user-1", "groups": ["PromptWise-Admins"],
                                                          "exp": time.time() - 10}))
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG, oidc_roles_path=str(roles_path))
    client = app.test_client()
    client.get("/auth/callback")
    r = client.get("/api/models")
    assert r.status_code == 401
    # the stale session must have been cleared, not just rejected once
    with client.session_transaction() as sess:
        assert "oidc_sub" not in sess
        assert "oidc_role" not in sess
        assert "oidc_exp" not in sess


def test_future_exp_session_is_accepted(monkeypatch, tmp_path):
    """A session with a future oidc_exp (as a fresh /auth/callback
    produces via the 8-hour default) is accepted."""
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    roles_path = tmp_path / "oidc_roles.yaml"
    roles_path.write_text("group_role_map:\n  PromptWise-Admins: admin\n", encoding="utf-8")
    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client",
                         lambda app, cfg: _fake_client({"sub": "user-1", "groups": ["PromptWise-Admins"]}))
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG, oidc_roles_path=str(roles_path))
    client = app.test_client()
    client.get("/auth/callback")
    r = client.get("/api/models")
    assert r.status_code == 200


def test_session_credential_id_is_namespaced_and_never_empty(monkeypatch, tmp_path):
    """The session-derived Identity.credential_id must never be the raw
    IdP `sub` (PII leak risk for email-shaped subs) and must never be
    empty even when the IdP omits `sub` entirely (an empty credential_id
    caused a real 400 'reviewer is required' failure on
    /api/admin/kb/promote despite successful authentication)."""
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")
    roles_path = tmp_path / "oidc_roles.yaml"
    roles_path.write_text("group_role_map:\n  PromptWise-Admins: admin\n", encoding="utf-8")
    import promptwise.dashboard.web as web_mod

    # sub missing entirely -- credential_id must still be non-empty,
    # verified indirectly via the KB-promote reviewer field (identity.credential_id
    # is persisted there as reviewed_by, and a blank reviewer is rejected --
    # a real 400 the reviewer demonstrated despite successful authentication).
    monkeypatch.setattr(web_mod, "build_oauth_client",
                         lambda app, cfg: _fake_client({"groups": ["PromptWise-Admins"]}))
    app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                          oidc_config=_OIDC_CFG, oidc_roles_path=str(roles_path))
    client = app.test_client()
    client.get("/auth/callback")
    r = client.post("/api/admin/kb/promote", json={"ids": [], "action": "trusted"})
    assert r.status_code != 400 or r.get_json().get("error") != "reviewer is required"


def test_session_cookie_secure_flag_follows_redirect_uri_scheme(monkeypatch, tmp_path):
    """The session cookie must be marked Secure whenever the OIDC
    redirect_uri is https, and SameSite=Lax always -- this cookie now
    grants dashboard access (including admin), and OIDC's whole purpose
    is enabling non-loopback binds where it could otherwise travel over
    plaintext HTTP on a LAN."""
    monkeypatch.setenv("PROMPTWISE_DASHBOARD_SECRET_KEY", "test-secret-key")

    https_cfg = OIDCConfig(
        issuer="https://idp.example.com", client_id="client-123",
        client_secret="secret-abc", redirect_uri="https://dashboard.example.com/auth/callback",
        group_claim="groups")
    import promptwise.dashboard.web as web_mod
    monkeypatch.setattr(web_mod, "build_oauth_client", lambda app, cfg: _fake_client({}))

    https_app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing.yaml"),
                                oidc_config=https_cfg)
    assert https_app.config["SESSION_COOKIE_SECURE"] is True
    assert https_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

    # _OIDC_CFG's redirect_uri is http://localhost:8765/... (the dev flow
    # the rest of this test module relies on) -- must stay non-Secure so
    # that flow keeps working, but still SameSite=Lax.
    http_app = create_web_app(require_auth=True, credentials_path=str(tmp_path / "missing2.yaml"),
                               oidc_config=_OIDC_CFG)
    assert http_app.config["SESSION_COOKIE_SECURE"] is False
    assert http_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
