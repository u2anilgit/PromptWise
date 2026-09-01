import os

from promptwise.dashboard.oidc_auth import (
    OIDCConfig, map_role_from_claims, load_group_role_map,
)


def test_oidc_config_from_env_returns_none_when_issuer_unset(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_OIDC_ISSUER", raising=False)
    assert OIDCConfig.from_env() is None


def test_oidc_config_from_env_reads_all_fields(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_OIDC_ISSUER", "https://idp.example.com")
    monkeypatch.setenv("PROMPTWISE_OIDC_CLIENT_ID", "client-123")
    monkeypatch.setenv("PROMPTWISE_OIDC_CLIENT_SECRET", "secret-abc")
    monkeypatch.setenv("PROMPTWISE_OIDC_REDIRECT_URI", "http://localhost:8765/auth/callback")
    cfg = OIDCConfig.from_env()
    assert cfg == OIDCConfig(
        issuer="https://idp.example.com", client_id="client-123",
        client_secret="secret-abc", redirect_uri="http://localhost:8765/auth/callback",
        group_claim="groups")


def test_oidc_config_from_env_honors_custom_group_claim(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_OIDC_ISSUER", "https://idp.example.com")
    monkeypatch.setenv("PROMPTWISE_OIDC_CLIENT_ID", "client-123")
    monkeypatch.setenv("PROMPTWISE_OIDC_CLIENT_SECRET", "secret-abc")
    monkeypatch.setenv("PROMPTWISE_OIDC_REDIRECT_URI", "http://localhost:8765/auth/callback")
    monkeypatch.setenv("PROMPTWISE_OIDC_GROUP_CLAIM", "roles")
    cfg = OIDCConfig.from_env()
    assert cfg.group_claim == "roles"


def test_map_role_from_claims_picks_highest_rank_when_multiple_match():
    claims = {"groups": ["PromptWise-Viewers", "PromptWise-Admins"]}
    role_map = {"PromptWise-Admins": "admin", "PromptWise-Viewers": "viewer"}
    assert map_role_from_claims(claims, "groups", role_map) == "admin"


def test_map_role_from_claims_defaults_to_viewer_when_no_match():
    claims = {"groups": ["Some-Other-Group"]}
    role_map = {"PromptWise-Admins": "admin"}
    assert map_role_from_claims(claims, "groups", role_map) == "viewer"


def test_map_role_from_claims_defaults_to_viewer_when_claim_missing():
    claims = {}
    role_map = {"PromptWise-Admins": "admin"}
    assert map_role_from_claims(claims, "groups", role_map) == "viewer"


def test_load_group_role_map_missing_file_returns_empty_dict(tmp_path):
    assert load_group_role_map(tmp_path / "does_not_exist.yaml") == {}


def test_load_group_role_map_reads_entries(tmp_path):
    p = tmp_path / "oidc_roles.yaml"
    p.write_text("group_role_map:\n  PromptWise-Admins: admin\n  PromptWise-Viewers: viewer\n", encoding="utf-8")
    assert load_group_role_map(p) == {"PromptWise-Admins": "admin", "PromptWise-Viewers": "viewer"}


def test_load_group_role_map_drops_entries_with_invalid_role(tmp_path):
    p = tmp_path / "oidc_roles.yaml"
    p.write_text("group_role_map:\n  Good-Group: admin\n  Bad-Group: superuser\n", encoding="utf-8")
    assert load_group_role_map(p) == {"Good-Group": "admin"}
