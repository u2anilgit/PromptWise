"""Device-scoped, ask-once routing consent -- see
docs/superpowers/specs/2026-07-24-three-quick-wins-design.md.
"""
from promptwise.core.routing_consent import RoutingConsent


def test_unknown_key_defaults_to_not_granted(tmp_path):
    rc = RoutingConsent(tmp_path / "consent.db")
    assert rc.is_granted("opus") is False


def test_grant_then_is_granted_round_trip(tmp_path):
    rc = RoutingConsent(tmp_path / "consent.db")
    rc.grant("opus")
    assert rc.is_granted("opus") is True


def test_grant_is_idempotent(tmp_path):
    rc = RoutingConsent(tmp_path / "consent.db")
    rc.grant("opus")
    rc.grant("opus")
    assert rc.is_granted("opus") is True


def test_revoke_clears_consent(tmp_path):
    rc = RoutingConsent(tmp_path / "consent.db")
    rc.grant("opus")
    rc.revoke("opus")
    assert rc.is_granted("opus") is False


def test_keys_are_independent(tmp_path):
    rc = RoutingConsent(tmp_path / "consent.db")
    rc.grant("opus")
    assert rc.is_granted("opus") is True
    assert rc.is_granted("some_other_key") is False


def test_persists_across_instances_same_db_path(tmp_path):
    db_path = tmp_path / "consent.db"
    RoutingConsent(db_path).grant("opus")
    assert RoutingConsent(db_path).is_granted("opus") is True
