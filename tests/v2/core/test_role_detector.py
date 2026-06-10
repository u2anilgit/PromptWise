"""
Tests for RoleDetector (auto-role detection from prompts).
"""

import pytest

from promptwise_v2.core.role_detector import RoleDetector, RoleDetectionResult


@pytest.fixture
def role_detector():
    """Create RoleDetector instance."""
    return RoleDetector()


class TestRoleDetectorInitialization:
    """Test RoleDetector initialization."""

    def test_init_with_defaults(self, role_detector):
        """Test initialization with default roles."""
        assert role_detector.roles_config is not None
        assert len(role_detector.roles_config) >= 15
        assert "developer" in role_detector.roles_config
        assert "analyst" in role_detector.roles_config


class TestRoleDeveloperDetection:
    """Test developer role detection."""

    def test_detect_developer_refactor(self, role_detector):
        """Test detecting developer role from refactoring task."""
        result = role_detector.detect("Refactor the payment module to use async/await")
        assert result.primary_role == "developer"
        assert result.confidence > 0.7
        assert "refactor" in [kw.lower() for kw in result.keywords_matched]

    def test_detect_developer_debug(self, role_detector):
        """Test detecting developer role from debugging task."""
        result = role_detector.detect("Debug this error in the API handler")
        assert result.primary_role == "developer"
        assert result.confidence > 0.6

    def test_detect_developer_code(self, role_detector):
        """Test detecting developer role from code request."""
        result = role_detector.detect("Write a function to parse JSON")
        assert result.primary_role == "developer"
        assert result.confidence > 0.6

    def test_detect_developer_test(self, role_detector):
        """Test detecting developer role from testing request."""
        result = role_detector.detect("Write unit tests for the auth module")
        assert result.primary_role == "developer"
        assert result.confidence > 0.6

    def test_detect_developer_class_definition(self, role_detector):
        """Test detecting developer from class definition pattern."""
        result = role_detector.detect("Create a class that implements the Observer pattern")
        assert result.primary_role == "developer"


class TestRoleAnalystDetection:
    """Test analyst role detection."""

    def test_detect_analyst_metrics(self, role_detector):
        """Test detecting analyst role from metrics request."""
        result = role_detector.detect("Analyze the Q1 revenue metrics by region")
        assert result.primary_role == "analyst"
        assert result.confidence > 0.7

    def test_detect_analyst_data(self, role_detector):
        """Test detecting analyst from data analysis."""
        result = role_detector.detect("Aggregate the sales data and calculate trends")
        assert result.primary_role == "analyst"
        assert result.confidence > 0.7

    def test_detect_analyst_sql(self, role_detector):
        """Test detecting analyst from SQL query request."""
        result = role_detector.detect("SELECT count(*) FROM users GROUP BY region")
        assert result.primary_role in ["analyst", "data"]
        assert result.confidence > 0.6

    def test_detect_analyst_pivot(self, role_detector):
        """Test detecting analyst from pivot request."""
        result = role_detector.detect("Create a pivot table showing sales by product")
        assert result.primary_role == "analyst"
        assert result.confidence > 0.6


class TestRoleManagerDetection:
    """Test manager role detection."""

    def test_detect_manager_timeline(self, role_detector):
        """Test detecting manager from timeline request."""
        result = role_detector.detect("What's the timeline for Q3 2026 roadmap?")
        assert result.primary_role == "manager"
        assert result.confidence > 0.7

    def test_detect_manager_sprint(self, role_detector):
        """Test detecting manager from sprint planning."""
        result = role_detector.detect("Plan the sprint for week 25")
        assert result.primary_role == "manager"
        assert result.confidence > 0.6

    def test_detect_manager_prioritization(self, role_detector):
        """Test detecting manager from prioritization request."""
        result = role_detector.detect("Help prioritize the backlog items")
        assert result.primary_role == "manager"
        assert result.confidence > 0.6


class TestRoleSecurityDetection:
    """Test security role detection."""

    def test_detect_security_auth(self, role_detector):
        """Test detecting security from auth context."""
        result = role_detector.detect("Review the authentication implementation for vulnerabilities")
        assert result.primary_role == "security"
        assert result.confidence > 0.7

    def test_detect_security_encryption(self, role_detector):
        """Test detecting security from encryption."""
        result = role_detector.detect("Implement end-to-end encryption for data")
        assert result.primary_role == "security"
        assert result.confidence > 0.6

    def test_detect_security_gdpr(self, role_detector):
        """Test detecting security from GDPR compliance."""
        result = role_detector.detect("GDPR compliance check on user data handling")
        assert result.primary_role == "security"
        assert result.confidence > 0.7

    def test_detect_security_cve(self, role_detector):
        """Test detecting security from CVE."""
        result = role_detector.detect("Patch CVE-2024-1234 vulnerability")
        assert result.primary_role == "security"
        assert result.confidence > 0.8


class TestRoleITDetection:
    """Test IT/DevOps role detection."""

    def test_detect_it_deploy(self, role_detector):
        """Test detecting IT from deployment request."""
        result = role_detector.detect("Deploy to us-east-1 with blue-green strategy")
        assert result.primary_role == "IT"
        assert result.confidence > 0.7

    def test_detect_it_kubernetes(self, role_detector):
        """Test detecting IT from Kubernetes context."""
        result = role_detector.detect("Scale the Kubernetes cluster for peak load")
        assert result.primary_role == "IT"
        assert result.confidence > 0.7

    def test_detect_it_docker(self, role_detector):
        """Test detecting IT from Docker."""
        result = role_detector.detect("Optimize the Docker image size")
        assert result.primary_role == "IT"
        assert result.confidence > 0.6

    def test_detect_it_terraform(self, role_detector):
        """Test detecting IT from Terraform."""
        result = role_detector.detect("Create Terraform modules for AWS infrastructure")
        assert result.primary_role == "IT"
        assert result.confidence > 0.6


class TestRoleDesignerDetection:
    """Test designer role detection."""

    def test_detect_designer_ui(self, role_detector):
        """Test detecting designer from UI context."""
        result = role_detector.detect("Design the user interface for the dashboard")
        assert result.primary_role == "designer"
        assert result.confidence > 0.7

    def test_detect_designer_ux(self, role_detector):
        """Test detecting designer from UX context."""
        result = role_detector.detect("Improve the user experience for mobile")
        assert result.primary_role == "designer"
        assert result.confidence > 0.6

    def test_detect_designer_responsive(self, role_detector):
        """Test detecting designer from responsive design."""
        result = role_detector.detect("Make the layout responsive for all devices")
        assert result.primary_role == "designer"
        assert result.confidence > 0.6


class TestRoleWriterDetection:
    """Test writer role detection."""

    def test_detect_writer_blog(self, role_detector):
        """Test detecting writer from blog post."""
        result = role_detector.detect("Write a blog post about AI trends")
        assert result.primary_role == "writer"
        assert result.confidence > 0.7

    def test_detect_writer_article(self, role_detector):
        """Test detecting writer from article."""
        result = role_detector.detect("Write an article on technical debt")
        assert result.primary_role == "writer"
        assert result.confidence > 0.6

    def test_detect_writer_content(self, role_detector):
        """Test detecting writer from content."""
        result = role_detector.detect("Create compelling content for the homepage")
        assert result.primary_role == "writer"
        assert result.confidence > 0.6


class TestRoleLegalDetection:
    """Test legal role detection."""

    def test_detect_legal_contract(self, role_detector):
        """Test detecting legal from contract."""
        result = role_detector.detect("Review the contract for compliance issues")
        assert result.primary_role == "legal"
        assert result.confidence > 0.7

    def test_detect_legal_gdpr(self, role_detector):
        """Test detecting legal from GDPR."""
        result = role_detector.detect("GDPR compliance audit for data processing")
        assert result.primary_role == "legal" or result.primary_role == "security"
        assert result.confidence > 0.6

    def test_detect_legal_ccpa(self, role_detector):
        """Test detecting legal from CCPA."""
        result = role_detector.detect("CCPA requirements for California users")
        assert result.primary_role == "legal"
        assert result.confidence > 0.7


class TestRoleHealthcareDetection:
    """Test healthcare role detection."""

    def test_detect_healthcare_hipaa(self, role_detector):
        """Test detecting healthcare from HIPAA."""
        result = role_detector.detect("Ensure HIPAA compliance for patient data")
        assert result.primary_role == "healthcare"
        assert result.confidence > 0.7

    def test_detect_healthcare_fhir(self, role_detector):
        """Test detecting healthcare from FHIR."""
        result = role_detector.detect("Implement FHIR standard for health records")
        assert result.primary_role == "healthcare"
        assert result.confidence > 0.7


class TestRoleDataDetection:
    """Test data engineer role detection."""

    def test_detect_data_sql(self, role_detector):
        """Test detecting data engineer from SQL."""
        result = role_detector.detect("Optimize the SQL query for large datasets")
        assert result.primary_role in ["data", "analyst"]
        assert result.confidence > 0.6

    def test_detect_data_etl(self, role_detector):
        """Test detecting data engineer from ETL."""
        result = role_detector.detect("Design an ETL pipeline for data warehouse")
        assert result.primary_role == "data"
        assert result.confidence > 0.7


class TestRoleQADetection:
    """Test QA role detection."""

    def test_detect_qa_test(self, role_detector):
        """Test detecting QA from test request."""
        result = role_detector.detect("Develop a comprehensive test strategy")
        assert result.primary_role == "qassurance"
        assert result.confidence > 0.6

    def test_detect_qa_automation(self, role_detector):
        """Test detecting QA from automation."""
        result = role_detector.detect("Automate tests using Playwright")
        assert result.primary_role == "qassurance"
        assert result.confidence > 0.7


class TestMultipleRoleScenarios:
    """Test scenarios with multiple detected roles."""

    def test_security_and_developer_refactoring(self, role_detector):
        """Test detecting security + developer for secure refactoring."""
        result = role_detector.detect("Refactor auth module to fix security vulnerability")
        assert result.primary_role == "developer" or result.primary_role == "security"
        assert len(result.secondary_roles) > 0

    def test_manager_and_developer_sprint(self, role_detector):
        """Test detecting manager + developer for sprint work."""
        result = role_detector.detect("Sprint planning: refactor API while fixing bugs")
        # Could be either depending on keyword emphasis
        assert result.primary_role in ["manager", "developer"]


class TestLowConfidenceScenarios:
    """Test low-confidence/ambiguous scenarios."""

    def test_general_role_default(self, role_detector):
        """Test falling back to general role for unclear prompts."""
        result = role_detector.detect("What is the weather today?")
        # Should have low confidence or detect as general
        assert result.confidence < 0.6 or result.primary_role == "general"

    def test_general_role_no_keywords(self, role_detector):
        """Test general role when no keywords match."""
        result = role_detector.detect("Tell me a story")
        # May detect writer or have low confidence
        assert result.confidence < 0.8 or result.primary_role == "writer"


class TestRoleConfidenceScoring:
    """Test confidence scoring."""

    def test_high_confidence_multiple_keywords(self, role_detector):
        """Test high confidence with multiple matching keywords."""
        result = role_detector.detect("Refactor the code for better readability, fix bugs, and implement unit tests")
        assert result.confidence > 0.7

    def test_lower_confidence_single_keyword(self, role_detector):
        """Test confidence with single keyword."""
        result = role_detector.detect("Deploy the app")
        # Single keyword may have moderate confidence
        assert 0.3 < result.confidence < 0.8


class TestRoleDetectionResult:
    """Test RoleDetectionResult dataclass."""

    def test_result_has_required_fields(self, role_detector):
        """Test that result has all required fields."""
        result = role_detector.detect("Refactor the code")

        assert hasattr(result, 'primary_role')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'secondary_roles')
        assert hasattr(result, 'keywords_matched')
        assert hasattr(result, 'rationale')

    def test_result_types(self, role_detector):
        """Test result field types."""
        result = role_detector.detect("Refactor the code")

        assert isinstance(result.primary_role, str)
        assert isinstance(result.confidence, float)
        assert isinstance(result.secondary_roles, list)
        assert isinstance(result.keywords_matched, list)
        assert isinstance(result.rationale, str)

    def test_confidence_in_valid_range(self, role_detector):
        """Test confidence is in 0-1 range."""
        result = role_detector.detect("Refactor the code")
        assert 0.0 <= result.confidence <= 1.0


class TestApplyRoleToPrompt:
    """Test role prefix application."""

    def test_apply_role_prefix_developer(self, role_detector):
        """Test applying developer prefix."""
        prompt = "Refactor this code"
        role_prefixes = {
            "developer": "From a software engineering perspective, "
        }

        result = role_detector.apply_role_to_prompt(prompt, "developer", role_prefixes)

        assert result.startswith("From a software engineering perspective,")
        assert "Refactor this code" in result

    def test_apply_role_prefix_general(self, role_detector):
        """Test applying general role (no prefix)."""
        prompt = "Help me with something"
        role_prefixes = {
            "general": ""
        }

        result = role_detector.apply_role_to_prompt(prompt, "general", role_prefixes)

        assert result == prompt

    def test_apply_role_prefix_missing_role(self, role_detector):
        """Test applying prefix for role not in config."""
        prompt = "Test prompt"
        role_prefixes = {}

        result = role_detector.apply_role_to_prompt(prompt, "unknown_role", role_prefixes)

        assert result == prompt
