"""WP1 1b -- approval workflow: request/resolve/list, resolve(approved)
mints a scoped JIT grant via the existing JITPermissions plumbing."""
import sqlite3
import time

from promptwise.core.approvals import Approvals
from promptwise.core.jit_permissions import JITPermissions


def test_request_creates_pending_record(tmp_path):
    a = Approvals(tmp_path / "approvals.db")
    rec = a.request("alice", "Bash:git push --force", {"reason": "hotfix"}, ttl_minutes=30)
    assert rec["status"] == "pending"
    assert rec["requester"] == "alice"
    assert rec["action_signature"] == "Bash:git push --force"
    assert rec["context"] == {"reason": "hotfix"}
    assert "id" in rec and isinstance(rec["id"], int)


def test_list_pending_returns_only_pending(tmp_path):
    a = Approvals(tmp_path / "approvals.db")
    r1 = a.request("alice", "Bash:git push --force", {})
    r2 = a.request("bob", "Bash:rm", {})
    a.resolve(r2["id"], "carol", "denied")
    pending = a.list_pending()
    ids = {p["id"] for p in pending}
    assert r1["id"] in ids
    assert r2["id"] not in ids


def test_resolve_approved_mints_jit_grant(tmp_path):
    db = tmp_path / "shared.db"
    a = Approvals(db)
    jp = JITPermissions(db)
    rec = a.request("alice", "Bash:git", {}, ttl_minutes=60)
    result = a.resolve(rec["id"], "carol", "approved", jit_ttl_minutes=15, jit_store=jp)
    assert result["status"] == "approved"
    assert result["resulting_jit_signature"] == "Bash:git"
    assert jp.is_active("Bash:git") is True


def test_resolve_denied_mints_no_jit_grant(tmp_path):
    db = tmp_path / "shared.db"
    a = Approvals(db)
    jp = JITPermissions(db)
    rec = a.request("alice", "Bash:rm", {}, ttl_minutes=60)
    result = a.resolve(rec["id"], "carol", "denied", jit_store=jp)
    assert result["status"] == "denied"
    assert result["resulting_jit_signature"] is None
    assert jp.is_active("Bash:rm") is False


def test_resolve_unknown_id_raises(tmp_path):
    a = Approvals(tmp_path / "approvals.db")
    try:
        a.resolve(999, "carol", "approved")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "999" in str(e)


def test_resolve_invalid_decision_raises(tmp_path):
    a = Approvals(tmp_path / "approvals.db")
    rec = a.request("alice", "Bash:git", {})
    try:
        a.resolve(rec["id"], "carol", "maybe")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "maybe" in str(e)


def test_get_returns_none_for_unknown_id(tmp_path):
    a = Approvals(tmp_path / "approvals.db")
    assert a.get(999) is None


def test_list_pending_excludes_expired_records(tmp_path):
    db = tmp_path / "approvals.db"
    a = Approvals(db)
    rec = a.request("alice", "Bash:git push --force", {}, ttl_minutes=1)

    # Backdate created_at so the 1-minute TTL has already lapsed.
    stale = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "UPDATE approvals SET created_at = ? WHERE id = ?",
            (stale, rec["id"]))
        conn.commit()
    finally:
        conn.close()

    pending = a.list_pending()
    ids = {p["id"] for p in pending}
    assert rec["id"] not in ids

    # Still retrievable directly, just excluded from the pending listing.
    stored = a.get(rec["id"])
    assert stored is not None
    assert stored["status"] == "pending"


def test_approval_chain_reconstructable_from_record(tmp_path):
    # who requested, who resolved, when, what grant resulted -- all on one row
    a = Approvals(tmp_path / "approvals.db")
    jp = JITPermissions(tmp_path / "approvals.db")
    rec = a.request("alice", "Bash:git", {"reason": "release"}, ttl_minutes=60)
    a.resolve(rec["id"], "carol", "approved", jit_ttl_minutes=30, jit_store=jp)
    stored = a.get(rec["id"])
    assert stored["requester"] == "alice"
    assert stored["resolver"] == "carol"
    assert stored["status"] == "approved"
    assert stored["resulting_jit_signature"] == "Bash:git"
    assert stored["resolved_at"] is not None
