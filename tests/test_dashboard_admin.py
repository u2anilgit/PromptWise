"""Dashboard Admin tab routes -- settings/feature/budget/KB review queue,
all gated by the existing require_role("admin") decorator in dashboard/web.py.

Auth fixture mirrors tests/test_dashboard_auth.py's real pattern: create_web_app
(there is no create_app in dashboard/web.py -- create_web_app is the factory)
with require_auth=True and a credentials_path yaml file containing a
credential_hash/role entry, then a request carries `Authorization: Bearer
<raw-credential>`.
"""
from promptwise.dashboard.auth import hash_credential
from promptwise.dashboard.web import create_web_app


def _write_credentials(path, role="admin", raw="admin-secret"):
    path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential(raw) + "\"\n    role: " + role + "\n",
        encoding="utf-8")


def _admin_app(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: tmp_path / "kb.json")
    cred_path = tmp_path / "dashboard_auth.yaml"
    _write_credentials(cred_path, role="admin", raw="admin-secret")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    app.config["TESTING"] = True
    return app


ADMIN_HEADERS = {"Authorization": "Bearer admin-secret"}


def test_admin_settings_requires_admin_role(tmp_path, monkeypatch):
    app = _admin_app(tmp_path, monkeypatch)
    client = app.test_client()
    resp = client.get("/api/admin/settings")
    # No credential header at all -- matches test_dashboard_auth.py's
    # test_require_auth_true_rejects_missing_header convention (401).
    assert resp.status_code == 401


def test_admin_settings_rejects_non_admin_role(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: tmp_path / "kb.json")
    cred_path = tmp_path / "dashboard_auth.yaml"
    _write_credentials(cred_path, role="viewer", raw="viewer-secret")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    client = app.test_client()
    resp = client.get("/api/admin/settings", headers={"Authorization": "Bearer viewer-secret"})
    assert resp.status_code == 403


def test_admin_settings_succeeds_for_admin_credential(tmp_path, monkeypatch):
    app = _admin_app(tmp_path, monkeypatch)
    client = app.test_client()
    resp = client.get("/api/admin/settings", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["features"] == {}
    # knowledgebase.enabled under the "knowledgebase" block is dead -- only
    # features["knowledgebase.enabled"] and knowledgebase.store_path are
    # ever read (finding #4). Assert what's actually consulted.
    assert body["features"].get("knowledgebase.enabled") is None
    assert body["knowledgebase"]["store_path"] is None


def test_set_feature_flag_via_admin_route_requires_auth(tmp_path, monkeypatch):
    app = _admin_app(tmp_path, monkeypatch)
    client = app.test_client()
    resp = client.post("/api/admin/feature", json={"name": "knowledgebase.enabled", "enabled": True})
    assert resp.status_code == 401


def test_set_feature_flag_via_admin_route_succeeds_for_admin(tmp_path, monkeypatch):
    app = _admin_app(tmp_path, monkeypatch)
    client = app.test_client()
    resp = client.post("/api/admin/feature", headers=ADMIN_HEADERS,
                        json={"name": "knowledgebase.enabled", "enabled": True})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["features"] == {"knowledgebase.enabled": True}
    assert body["project_features"] == {}


def test_admin_budget_route_succeeds_for_admin(tmp_path, monkeypatch):
    app = _admin_app(tmp_path, monkeypatch)
    client = app.test_client()
    resp = client.post("/api/admin/budget", headers=ADMIN_HEADERS,
                        json={"limit_usd": 250.0, "period": "monthly"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["limit_usd"] == 250.0


def test_admin_kb_unreviewed_route_succeeds_for_admin(tmp_path, monkeypatch):
    app = _admin_app(tmp_path, monkeypatch)
    from promptwise.core.knowledgebase import FileBackend, KnowledgeEntry
    FileBackend(store_path=tmp_path / "kb.json").save_entry(KnowledgeEntry(
        id="e1", title="cache-aside", tags=["cache-aside"], summary="s",
        source_prompt="speed up reads", artifact_ref="", status="unreviewed",
        created_by="sess", created_at="2026-08-20T00:00:00Z"))
    client = app.test_client()
    resp = client.get("/api/admin/kb/unreviewed", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["entries"][0]["id"] == "e1"


def test_admin_kb_promote_route_succeeds_for_admin(tmp_path, monkeypatch):
    app = _admin_app(tmp_path, monkeypatch)
    from promptwise.core.knowledgebase import FileBackend, KnowledgeEntry
    FileBackend(store_path=tmp_path / "kb.json").save_entry(KnowledgeEntry(
        id="e1", title="cache-aside", tags=["cache-aside"], summary="s",
        source_prompt="speed up reads", artifact_ref="", status="unreviewed",
        created_by="sess", created_at="2026-08-20T00:00:00Z"))
    client = app.test_client()
    resp = client.post("/api/admin/kb/promote", headers=ADMIN_HEADERS,
                        json={"ids": ["e1"], "action": "trusted", "reviewer": "alice"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["promoted"] == ["e1"]


def test_admin_kb_promote_route_requires_admin(tmp_path, monkeypatch):
    app = _admin_app(tmp_path, monkeypatch)
    client = app.test_client()
    resp = client.post("/api/admin/kb/promote", json={"ids": ["e1"], "action": "trusted", "reviewer": "alice"})
    assert resp.status_code == 401
