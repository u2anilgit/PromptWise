"""Regression tests for the 2026-08-20 whole-branch review findings #5, #7,
#8 on the dashboard Admin tab routes."""
import json

from promptwise.dashboard.auth import hash_credential
from promptwise.dashboard.web import create_web_app
from promptwise.plugins.budget import BudgetGuardian


def _write_credentials(path, role="admin", raw="admin-secret"):
    path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential(raw) + "\"\n    role: " + role + "\n",
        encoding="utf-8")


def test_admin_budget_route_persists_to_the_shared_guardian(tmp_path, monkeypatch):
    """finding #5: /api/admin/budget must mutate the SAME BudgetGuardian
    instance /api/budget reads from -- not a fresh throwaway that's
    discarded after the request."""
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    guardian = BudgetGuardian()
    app = create_web_app(budget_guardian=guardian)
    client = app.test_client()

    resp = client.post("/api/admin/budget", json={"limit_usd": 777.0, "period": "monthly"})
    assert resp.status_code == 200

    # Visible directly on the shared instance...
    assert guardian.limit_usd == 777.0
    # ...and via the read route, which must consult the same instance.
    r2 = client.get("/api/budget")
    assert r2.get_json()["limit_usd"] == 777.0


def test_admin_feature_route_rejects_body_without_declared_content_type(tmp_path, monkeypatch):
    """finding #7: dropping force=True means a POST body must actually be
    declared application/json (browsers require a CORS preflight for a
    cross-origin form to set that header), closing the CSRF-shaped drive-by
    vector when require_auth is False."""
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    app = create_web_app()
    client = app.test_client()

    # Simulates a plain HTML form POST (text/plain or
    # application/x-www-form-urlencoded) -- Flask's get_json(silent=True)
    # without force=True must NOT parse this as JSON.
    resp = client.post("/api/admin/feature", data=json.dumps({"name": "x", "enabled": True}),
                        content_type="text/plain")
    body = resp.get_json()
    # The text/plain body must NOT be parsed as JSON -- get_json(silent=True)
    # without force=True degrades to {}, so set_feature_flag never sees the
    # injected name="x"/enabled=True payload.
    assert "x" not in body["features"]


def test_admin_kb_promote_rejects_blank_reviewer(tmp_path, monkeypatch):
    """finding #8: the dashboard route must enforce the same non-empty
    reviewer gate promote_kb_candidates enforces -- no silent bypass."""
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: tmp_path / "kb.json")
    from promptwise.core.knowledgebase import FileBackend, KnowledgeEntry
    FileBackend(store_path=tmp_path / "kb.json").save_entry(KnowledgeEntry(
        id="e1", title="t", tags=[], summary="s", source_prompt="p", artifact_ref="",
        status="unreviewed", created_by="sess", created_at="2026-08-20T00:00:00Z"))

    app = create_web_app()
    client = app.test_client()
    resp = client.post("/api/admin/kb/promote", json={"ids": ["e1"], "action": "trusted", "reviewer": "  "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()

    # entry must remain unreviewed -- the bypass never took effect.
    entries = FileBackend(store_path=tmp_path / "kb.json").list_entries(status="unreviewed")
    assert len(entries) == 1


def test_admin_kb_promote_uses_authenticated_identity_as_reviewer(tmp_path, monkeypatch):
    """finding #8: when auth is enforced, the reviewer recorded must be the
    authenticated identity's credential_id, not a client-supplied string."""
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: tmp_path / "kb.json")
    from promptwise.core.knowledgebase import FileBackend, KnowledgeEntry
    FileBackend(store_path=tmp_path / "kb.json").save_entry(KnowledgeEntry(
        id="e1", title="t", tags=[], summary="s", source_prompt="p", artifact_ref="",
        status="unreviewed", created_by="sess", created_at="2026-08-20T00:00:00Z"))

    cred_path = tmp_path / "dashboard_auth.yaml"
    _write_credentials(cred_path, role="admin", raw="admin-secret")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    client = app.test_client()

    resp = client.post("/api/admin/kb/promote", headers={"Authorization": "Bearer admin-secret"},
                        json={"ids": ["e1"], "action": "trusted", "reviewer": "spoofed-name"})
    assert resp.status_code == 200

    entry = FileBackend(store_path=tmp_path / "kb.json").get_entry("e1")
    assert entry.reviewed_by != "spoofed-name"
    from promptwise.dashboard.auth import hash_credential
    assert entry.reviewed_by == hash_credential("admin-secret")[:12]


def test_admin_kb_promote_rejects_invalid_action(tmp_path, monkeypatch):
    """minor: the dashboard route must validate action against
    VALID_STATUSES, matching the MCP tool's own schema enum."""
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: tmp_path / "kb.json")
    app = create_web_app()
    client = app.test_client()
    resp = client.post("/api/admin/kb/promote",
                        json={"ids": ["e1"], "action": "not-a-real-status", "reviewer": "alice"})
    assert resp.status_code == 400
