import pytest
from promptwise_v2.core.role_intelligence import RoleIntelligence


@pytest.fixture
def ri():
    return RoleIntelligence()


def test_detect_developer_role(ri):
    profile = ri.detect("Fix this Python function, the unit tests are failing")
    assert profile.role == "developer"
    assert profile.confidence >= 0.6
    assert profile.recommended_model_tier == "balanced"


def test_detect_analyst_role(ri):
    profile = ri.detect("Analyze the trend data and generate a metrics report")
    assert profile.role == "analyst"


def test_detect_researcher_role(ri):
    profile = ri.detect("Research and synthesize novel approaches to transformer attention")
    assert profile.role == "researcher"
    assert profile.recommended_model_tier == "powerful"


def test_detect_manager_role(ri):
    profile = ri.detect("Summarize project status and create a stakeholder update")
    assert profile.role == "manager"


def test_detect_writer_role(ri):
    profile = ri.detect("Draft a blog post about AI trends")
    assert profile.role == "writer"


def test_detect_designer_role(ri):
    profile = ri.detect("Design a UI component with proper accessibility")
    assert profile.role == "designer"


def test_confidence_range(ri):
    profile = ri.detect("Hello world")
    assert 0.0 <= profile.confidence <= 1.0


def test_explanation_mode(ri):
    profile = ri.detect("Explain how this code works", explanation_mode=True)
    assert "explain" in profile.context_hint.lower()
