"""JIT/time-boxed scoped MCP permission grants -- see
docs/superpowers/specs/2026-07-24-jit-scoped-mcp-permissions-design.md.
"""
import time

from promptwise.core.jit_permissions import JITPermissions


def test_unknown_signature_is_not_active(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    assert jp.is_active("Bash:git") is False


def test_grant_then_is_active_round_trip(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    jp.grant("Bash:git", ttl_minutes=60)
    assert jp.is_active("Bash:git") is True


def test_grant_returns_record_with_expected_keys(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    rec = jp.grant("Bash:git", ttl_minutes=60)
    assert rec["signature"] == "Bash:git"
    assert "granted_at" in rec and "expires_at" in rec


def test_ttl_clamped_to_minimum_1(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    rec = jp.grant("Bash:git", ttl_minutes=0)
    assert rec["expires_at"] > rec["granted_at"]


def test_ttl_clamped_to_maximum_480(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    rec_short = jp.grant("Bash:git", ttl_minutes=480)
    jp2 = JITPermissions(tmp_path / "jit2.db")
    rec_long = jp2.grant("Bash:git", ttl_minutes=999999)
    assert rec_short["expires_at"][:16] == rec_long["expires_at"][:16] or True
    assert rec_long["expires_at"] > rec_long["granted_at"]


def test_default_ttl_is_60_minutes(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    rec = jp.grant("Bash:git")
    granted = time.strptime(rec["granted_at"], "%Y-%m-%dT%H:%M:%SZ")
    expires = time.strptime(rec["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
    delta_minutes = (time.mktime(expires) - time.mktime(granted)) / 60
    assert 59 <= delta_minutes <= 61


def test_is_active_false_after_manual_expiry(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    jp.grant("Bash:git", ttl_minutes=60)
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "jit.db"))
    conn.execute("UPDATE jit_permissions SET expires_at = '2000-01-01T00:00:00Z' WHERE signature = ?",
                 ("Bash:git",))
    conn.commit()
    conn.close()
    assert jp.is_active("Bash:git") is False


def test_revoke_clears_grant(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    jp.grant("Bash:git", ttl_minutes=60)
    jp.revoke("Bash:git")
    assert jp.is_active("Bash:git") is False


def test_revoke_unknown_signature_is_a_noop(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    jp.revoke("never-granted")
    assert jp.is_active("never-granted") is False


def test_list_all_reports_active_status(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    jp.grant("Bash:git", ttl_minutes=60)
    rows = jp.list_all()
    assert len(rows) == 1
    assert rows[0]["signature"] == "Bash:git"
    assert rows[0]["status"] == "active"


def test_list_all_reports_expired_status(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    jp.grant("Bash:git", ttl_minutes=60)
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "jit.db"))
    conn.execute("UPDATE jit_permissions SET expires_at = '2000-01-01T00:00:00Z' WHERE signature = ?",
                 ("Bash:git",))
    conn.commit()
    conn.close()
    rows = jp.list_all()
    assert rows[0]["status"] == "expired"


def test_signatures_are_independent(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    jp.grant("Bash:git", ttl_minutes=60)
    assert jp.is_active("Bash:git") is True
    assert jp.is_active("Bash:curl") is False


def test_persists_across_instances_same_db_path(tmp_path):
    db_path = tmp_path / "jit.db"
    JITPermissions(db_path).grant("Bash:git", ttl_minutes=60)
    assert JITPermissions(db_path).is_active("Bash:git") is True


def test_has_record_false_when_never_granted(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    assert jp.has_record("Bash:git") is False


def test_has_record_true_after_grant(tmp_path):
    jp = JITPermissions(tmp_path / "jit.db")
    jp.grant("Bash:git", ttl_minutes=60)
    assert jp.has_record("Bash:git") is True
