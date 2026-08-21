from promptwise.security.agentic_framework_map import ASI_SOURCE
from promptwise.security.framework_map import FRAMEWORK_SOURCES, gap_analysis


def test_owasp_agentic_top10_has_all_ten_asi_controls():
    result = gap_analysis("owasp_agentic_top10", registered_tools=[])
    ids = {c["control_id"] for c in result["controls"]}
    assert ids == {f"ASI{i:02d}" for i in range(1, 11)}


def test_owasp_agentic_top10_reuses_verified_asi_source_not_reinvented():
    result = gap_analysis("owasp_agentic_top10", registered_tools=[])
    assert result["source"]["url"] == ASI_SOURCE["url"]
    assert result["source"]["fetched"] == ASI_SOURCE["fetched"]
    assert FRAMEWORK_SOURCES["owasp_agentic_top10"]["url"] == ASI_SOURCE["url"]


def test_asi06_memory_context_poisoning_evidenced_by_wp6_own_tools():
    result = gap_analysis("owasp_agentic_top10", registered_tools=["context_lineage", "score_context_quality"])
    control = next(c for c in result["controls"] if c["control_id"] == "ASI06")
    assert control["status"] == "implemented"
    assert set(control["evidenced_by"]) == {"context_lineage", "score_context_quality"}


def test_asi10_rogue_agents_matches_wp5_scenario_tools():
    result = gap_analysis("owasp_agentic_top10", registered_tools=["detect_agent_drift", "create_incident"])
    control = next(c for c in result["controls"] if c["control_id"] == "ASI10")
    assert control["status"] == "implemented"


def test_asi_titles_match_the_verified_official_category_names():
    result = gap_analysis("owasp_agentic_top10", registered_tools=[])
    by_id = {c["control_id"]: c["title"] for c in result["controls"]}
    assert by_id["ASI01"] == "Agent Goal Hijack"
    assert by_id["ASI06"] == "Memory & Context Poisoning"
    assert by_id["ASI10"] == "Rogue Agents"
