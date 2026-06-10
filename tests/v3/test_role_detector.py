"""Tests for unified RoleDetector."""

from promptwise_v3.core.role_detector import RoleDetector


def test_detect_developer():
    d = RoleDetector()
    r = d.detect("Write a Python function to sort an array")
    assert r.primary_role == "developer"
    assert r.confidence > 0.5


def test_detect_security():
    d = RoleDetector()
    r = d.detect("Check for injection vulnerabilities CVE-2024-1234 and OWASP top 10")
    assert r.primary_role == "security"
    assert r.confidence > 0.5


def test_detect_analyst():
    d = RoleDetector()
    r = d.detect("Analyze this dataset and create a chart with monthly metrics")
    assert r.primary_role == "analyst"


def test_detect_data():
    d = RoleDetector()
    r = d.detect("Write a SQL query to join users and orders tables")
    assert r.primary_role == "data"


def test_detect_designer():
    d = RoleDetector()
    r = d.detect("Design a responsive UI component with CSS")
    assert r.primary_role == "designer"


def test_detect_legal():
    d = RoleDetector()
    r = d.detect("Review this GDPR compliance contract")
    assert r.primary_role == "legal"


def test_detect_healthcare():
    d = RoleDetector()
    r = d.detect("Ensure HIPAA compliance for patient data handling")
    assert r.primary_role == "healthcare"


def test_detect_finance():
    d = RoleDetector()
    r = d.detect("Audit FINRA compliance for trading records")
    assert r.primary_role == "finance"


def test_detect_pm():
    d = RoleDetector()
    r = d.detect("Write user stories for the new feature epic")
    assert r.primary_role == "pm"


def test_detect_executive():
    d = RoleDetector()
    r = d.detect("Calculate ROI and growth strategy for Q3")
    assert r.primary_role == "executive"


def test_detect_writer():
    d = RoleDetector()
    r = d.detect("Draft a blog post about cloud architecture")
    assert r.primary_role == "writer"


def test_detect_researcher():
    d = RoleDetector()
    r = d.detect("Analyze study methodology and experimental results")
    assert r.primary_role == "researcher"


def test_detect_general_fallback():
    d = RoleDetector()
    r = d.detect("Hello, how are you?")
    assert r.confidence < 0.5


def test_get_recommended_tier():
    d = RoleDetector()
    tier = d.get_recommended_tier("security")
    assert tier == "powerful"


def test_detect_with_file_context():
    d = RoleDetector()
    r = d.detect("SELECT * FROM users", context={"file_type": "sql"})
    assert r.primary_role == "data"
