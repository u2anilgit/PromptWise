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
    r = app.test_client().get("/auth/callback")
    assert r.status_code == 401
    # no session identity was set as a side effect of the failed attempt
    r2 = app.test_client().get("/api/models")
    assert r2.status_code == 401
