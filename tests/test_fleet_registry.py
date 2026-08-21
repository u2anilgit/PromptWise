from promptwise.core.fleet import FleetRegistry


def _registry(tmp_path):
    return FleetRegistry(db_path=tmp_path / "fleet.db")


def test_register_creates_new_agent(tmp_path):
    reg = _registry(tmp_path)
    rec = reg.register(
        "agent-alpha", role="read-only-reviewer", responsibilities=["code review"],
        allowed_tools=["Read", "Grep"], budget_usd=10.0, priority="high", owner="team-x",
        scoped_credential=True, last_rotation_date="2026-08-01", jit_grant_signature="Bash:git")
    assert rec["agent_id"] == "agent-alpha"
    assert rec["allowed_tools"] == ["Read", "Grep"]
    assert rec["scoped_credential"] is True
    assert rec["priority"] == "high"
    assert rec["registered_at"]
    assert rec["last_drift_score"] == 0.0


def test_register_upserts_existing_agent(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-alpha", role="reviewer", allowed_tools=["Read"])
    updated = reg.register("agent-alpha", role="reviewer-v2", allowed_tools=["Read", "Grep"])
    assert updated["role"] == "reviewer-v2"
    assert updated["allowed_tools"] == ["Read", "Grep"]
    assert len(reg.list_all()) == 1


def test_get_unknown_agent_returns_none(tmp_path):
    reg = _registry(tmp_path)
    assert reg.get("nope") is None


def test_list_all_returns_every_registered_agent(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="r1", allowed_tools=["Read"])
    reg.register("agent-b", role="r2", allowed_tools=["Write"])
    ids = {r["agent_id"] for r in reg.list_all()}
    assert ids == {"agent-a", "agent-b"}


def test_update_drift_persists_score(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="r1", allowed_tools=["Read"])
    reg.update_drift("agent-a", 72.5, "2026-08-21T00:00:00Z")
    rec = reg.get("agent-a")
    assert rec["last_drift_score"] == 72.5
    assert rec["last_drift_checked_at"] == "2026-08-21T00:00:00Z"


def test_update_drift_unknown_agent_is_fail_soft(tmp_path):
    reg = _registry(tmp_path)
    reg.update_drift("unknown", 99.0, "2026-08-21T00:00:00Z")  # must not raise


def test_delete_removes_agent(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="r1", allowed_tools=["Read"])
    reg.delete("agent-a")
    assert reg.get("agent-a") is None
