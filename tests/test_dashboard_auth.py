"""Dashboard auth/RBAC -- see docs/superpowers/specs/2026-07-23-dashboard-auth-rbac-design.md.

The dashboard's Flask app had zero authentication and cli.py hardcoded
host="0.0.0.0", so a solo dev running `promptwise serve` unknowingly
exposed cost/governance data to their entire LAN. This file locks in:
default bind is loopback-only, auth is opt-in via a local credential file,
and role-based access control gates every /api/* route once enabled.
"""
import hashlib
from pathlib import Path

from promptwise.config import AppConfig, DashboardConfig
from promptwise.dashboard.auth import (
    Identity, hash_credential, load_credentials, find_identity,
)


def test_dashboard_config_defaults_to_loopback_host():
    cfg = AppConfig()
    assert cfg.dashboard.web_host == "127.0.0.1"


def test_dashboard_config_web_host_overridable():
    cfg = DashboardConfig(web_host="0.0.0.0")
    assert cfg.web_host == "0.0.0.0"


def test_hash_credential_is_sha256_hex():
    assert hash_credential("my-raw-value") == hashlib.sha256(b"my-raw-value").hexdigest()


def test_load_credentials_missing_file_returns_empty_list(tmp_path):
    assert load_credentials(tmp_path / "does_not_exist.yaml") == []


def test_load_credentials_reads_entries(tmp_path):
    p = tmp_path / "dashboard_auth.yaml"
    p.write_text(
        "entries:\n"
        "  - credential_hash: \"" + hash_credential("abc") + "\"\n"
        "    role: admin\n",
        encoding="utf-8")
    entries = load_credentials(p)
    assert len(entries) == 1
    assert entries[0]["role"] == "admin"


def test_find_identity_matches_valid_credential():
    entries = [{"credential_hash": hash_credential("abc"), "role": "viewer", "projects": None}]
    identity = find_identity("abc", entries)
    assert identity == Identity(credential_id=hash_credential("abc")[:12], role="viewer", projects=None)


def test_find_identity_returns_none_for_unknown_credential():
    entries = [{"credential_hash": hash_credential("abc"), "role": "viewer"}]
    assert find_identity("wrong-value", entries) is None


def test_find_identity_returns_none_for_empty_credentials_list():
    assert find_identity("anything", []) is None


from promptwise.dashboard.web import create_web_app


def test_require_auth_false_is_default_and_needs_no_header():
    app = create_web_app()
    r = app.test_client().get("/api/models")
    assert r.status_code == 200


def test_require_auth_true_rejects_missing_header(tmp_path):
    cred_path = tmp_path / "dashboard_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: viewer\n",
        encoding="utf-8")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    r = app.test_client().get("/api/models")
    assert r.status_code == 401


def test_require_auth_true_rejects_unknown_credential(tmp_path):
    cred_path = tmp_path / "dashboard_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: viewer\n",
        encoding="utf-8")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    r = app.test_client().get("/api/models", headers={"Authorization": "Bearer wrong-value"})
    assert r.status_code == 401


def test_require_auth_true_accepts_valid_viewer_credential(tmp_path):
    cred_path = tmp_path / "dashboard_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: viewer\n",
        encoding="utf-8")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    r = app.test_client().get("/api/models", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 200


def test_index_route_never_requires_auth(tmp_path):
    # "/" only serves the static HTML shell (no data) -- always open so the
    # page can load and its own JS then hits the (gated) /api/* routes.
    cred_path = tmp_path / "dashboard_auth.yaml"
    cred_path.write_text("entries: []\n", encoding="utf-8")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    r = app.test_client().get("/")
    assert r.status_code == 200
