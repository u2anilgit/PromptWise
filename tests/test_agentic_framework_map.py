"""Task 5 -- OWASP Top 10 for Agentic Applications (2026, ASI01-ASI10) mapping.

Maps this repo's WP2 agentic-attack corpus families (``corpus/wp2_agentic_candidates.json``,
``family`` field) onto the official ASI01-ASI10 categories, following the same
anti-fabrication discipline as ``framework_map.py`` / ``mcp_auditor.py``: this
test file only asserts the mapping, not the citations (see the module
docstring in ``agentic_framework_map.py`` for the verified source/date).
"""
from promptwise.security.agentic_framework_map import (
    ASI_SOURCE,
    coverage_matrix,
    map_family_to_asi,
)


def test_memory_poisoning_maps_to_asi06():
    assert map_family_to_asi("memory_poisoning") == "ASI06 Memory & Context Poisoning"


def test_goal_hijack_maps_to_asi01():
    assert map_family_to_asi("goal_hijack") == "ASI01 Agent Goal Hijack"


def test_fake_approval_agent_maps_to_asi10():
    assert map_family_to_asi("fake_approval_agent") == "ASI10 Rogue Agents"


def test_readme_instruction_injection_maps_to_asi02():
    assert map_family_to_asi("readme_instruction_injection") == "ASI02 Tool Misuse and Exploitation"


def test_unmapped_family_returns_none_not_guessed():
    assert map_family_to_asi("not_a_real_family") is None


def test_source_citation_present():
    assert ASI_SOURCE["url"].startswith("https://genai.owasp.org/")
    assert ASI_SOURCE["fetched"]


def test_coverage_matrix_separates_mapped_and_unmapped():
    result = coverage_matrix(["memory_poisoning", "not_a_real_family"])
    assert result["mapped"] == {"memory_poisoning": "ASI06 Memory & Context Poisoning"}
    assert result["unmapped"] == ["not_a_real_family"]


def test_coverage_matrix_covers_all_four_corpus_families():
    families = ["goal_hijack", "memory_poisoning", "fake_approval_agent", "readme_instruction_injection"]
    result = coverage_matrix(families)
    assert result["unmapped"] == []
    assert set(result["mapped"]) == set(families)
