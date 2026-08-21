from promptwise.core.fleet import FleetRegistry, detect_sprawl


def _registry(tmp_path):
    return FleetRegistry(db_path=tmp_path / "fleet.db")


def test_detect_sprawl_flags_high_tool_overlap(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="reviewer", allowed_tools=["Read", "Grep", "Glob"])
    reg.register("agent-b", role="linter", allowed_tools=["Read", "Grep", "Bash"])
    result = detect_sprawl(reg, jaccard_threshold=0.4)
    assert len(result["pairs"]) == 1
    pair = result["pairs"][0]
    assert {pair["agent_a"], pair["agent_b"]} == {"agent-a", "agent-b"}
    assert pair["shared_tools"] == ["Grep", "Read"]
    # jaccard = |{Read,Grep}| / |{Read,Grep,Glob,Bash}| = 2/4 = 0.5
    assert pair["jaccard"] == 0.5


def test_detect_sprawl_below_threshold_not_reported(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="reviewer", allowed_tools=["Read"])
    reg.register("agent-b", role="writer", allowed_tools=["Write"])
    result = detect_sprawl(reg, jaccard_threshold=0.4)
    assert result["pairs"] == []


def test_detect_sprawl_empty_tool_sets_never_match(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="idle", allowed_tools=[])
    reg.register("agent-b", role="idle", allowed_tools=[])
    result = detect_sprawl(reg, jaccard_threshold=0.0)
    assert result["pairs"] == []


def test_detect_sprawl_flags_role_duplication(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="deploy-bot", allowed_tools=["Bash"])
    reg.register("agent-b", role="deploy-bot", allowed_tools=["Write"])
    reg.register("agent-c", role="reviewer", allowed_tools=["Read"])
    result = detect_sprawl(reg, jaccard_threshold=0.9)
    assert result["role_duplicates"] == {"deploy-bot": ["agent-a", "agent-b"]}


def test_detect_sprawl_fewer_than_two_agents_returns_empty(tmp_path):
    reg = _registry(tmp_path)
    reg.register("agent-a", role="solo", allowed_tools=["Read"])
    result = detect_sprawl(reg)
    assert result == {"pairs": [], "role_duplicates": {}}
