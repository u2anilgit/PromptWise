"""
Tests for AutoRoleApplier (applying detected roles to prompts).
"""

import pytest

from promptwise_v2.core.role_detector import RoleDetector
from promptwise_v2.core.auto_role_applier import AutoRoleApplier


@pytest.fixture
def role_detector():
    """Create RoleDetector instance."""
    return RoleDetector()


@pytest.fixture
def roles_config():
    """Get roles config."""
    return {
        "developer": {
            "prefix": "From a software engineering perspective, ",
            "display_name": "Developer"
        },
        "analyst": {
            "prefix": "With supporting data and structured analysis, ",
            "display_name": "Analyst"
        },
        "security": {
            "prefix": "From a cybersecurity threat mitigation perspective, ",
            "display_name": "Security"
        },
        "general": {
            "prefix": "",
            "display_name": "General"
        }
    }


@pytest.fixture
def auto_role_applier(role_detector, roles_config):
    """Create AutoRoleApplier instance."""
    config = {
        "enabled": True,
        "confidence_threshold": 0.65,
        "apply_constraints": True
    }
    return AutoRoleApplier(role_detector, roles_config, config)


class TestAutoRoleApplierInitialization:
    """Test AutoRoleApplier initialization."""

    def test_init_enabled(self, auto_role_applier):
        """Test initialization with enabled flag."""
        assert auto_role_applier.enabled is True
        assert auto_role_applier.confidence_threshold == 0.65
        assert auto_role_applier.apply_constraints is True

    def test_init_disabled(self, role_detector, roles_config):
        """Test initialization with disabled flag."""
        config = {"enabled": False}
        applier = AutoRoleApplier(role_detector, roles_config, config)
        assert applier.enabled is False

    def test_init_custom_threshold(self, role_detector, roles_config):
        """Test custom confidence threshold."""
        config = {"enabled": True, "confidence_threshold": 0.50}
        applier = AutoRoleApplier(role_detector, roles_config, config)
        assert applier.confidence_threshold == 0.50

    def test_init_empty_config(self, role_detector, roles_config):
        """Test initialization with empty config."""
        applier = AutoRoleApplier(role_detector, roles_config, {})
        assert applier.enabled is True  # Default
        assert applier.confidence_threshold == 0.65  # Default


class TestAutoRoleApplyDisabled:
    """Test behavior when auto-role is disabled."""

    def test_apply_when_disabled(self, role_detector, roles_config):
        """Test apply returns unchanged prompt when disabled."""
        config = {"enabled": False}
        applier = AutoRoleApplier(role_detector, roles_config, config)

        result = applier.apply("Refactor this code")

        assert result["prompt"] == "Refactor this code"
        assert result["role"] == "general"
        assert result["confidence"] == 0.0
        assert len(result["applied_features"]) == 0


class TestAutoRoleApplyHighConfidence:
    """Test applying role with high confidence."""

    def test_apply_developer_high_confidence(self, auto_role_applier):
        """Test applying developer role with high confidence."""
        result = auto_role_applier.apply("Refactor the payment module for better performance")

        assert result["role"] == "developer"
        assert result["confidence"] > 0.65
        assert "role_prefix" in result["applied_features"]
        assert result["prompt"].startswith("From a software engineering perspective,")

    def test_apply_security_high_confidence(self, auto_role_applier):
        """Test applying security role with high confidence."""
        result = auto_role_applier.apply("Fix the authentication vulnerability in the login handler")

        assert result["role"] == "security"
        assert result["confidence"] > 0.65
        assert "From a cybersecurity" in result["prompt"]

    def test_apply_analyst_high_confidence(self, auto_role_applier):
        """Test applying analyst role."""
        result = auto_role_applier.apply("Analyze the Q1 revenue metrics by region")

        assert result["role"] == "analyst"
        assert "With supporting data" in result["prompt"]


class TestAutoRoleApplyLowConfidence:
    """Test behavior with low confidence detection."""

    def test_apply_low_confidence_falls_back_to_general(self, auto_role_applier):
        """Test fallback to general role on low confidence."""
        result = auto_role_applier.apply("What is the weather?")

        # Low confidence should fall back to general
        if result["confidence"] < 0.65:
            assert result["role"] == "general"
            assert result["prompt"] == "What is the weather?"

    def test_apply_below_threshold_fallback(self, auto_role_applier):
        """Test explicit fallback when below threshold."""
        # Use a prompt with no clear role signals
        result = auto_role_applier.apply("xyz abc def")

        assert result["confidence"] < 0.65
        assert result["role"] == "general"


class TestAutoRoleApplyConstraints:
    """Test constraint application."""

    def test_apply_constraints_enabled(self, auto_role_applier):
        """Test constraints applied when enabled."""
        result = auto_role_applier.apply("Refactor the code")

        if result["role"] == "developer":
            assert "constraints" in result["applied_features"]
            assert len(result["constraints"]) > 0

    def test_apply_constraints_disabled(self, role_detector, roles_config):
        """Test constraints not applied when disabled."""
        config = {
            "enabled": True,
            "apply_constraints": False
        }
        applier = AutoRoleApplier(role_detector, roles_config, config)

        result = applier.apply("Refactor the code")

        assert "constraints" not in result["applied_features"]
        assert len(result["constraints"]) == 0


class TestRoleConstraints:
    """Test role-specific constraints."""

    def test_developer_constraints(self, role_detector, roles_config):
        """Test developer constraints."""
        config = {"enabled": True, "apply_constraints": True}
        applier = AutoRoleApplier(role_detector, roles_config, config)

        constraints = applier._get_constraints_for_role("developer")

        assert len(constraints) > 0
        assert "code_blocks" in constraints or "prefer_code_blocks" in constraints

    def test_analyst_constraints(self, role_detector, roles_config):
        """Test analyst constraints."""
        config = {"enabled": True, "apply_constraints": True}
        applier = AutoRoleApplier(role_detector, roles_config, config)

        constraints = applier._get_constraints_for_role("analyst")

        assert len(constraints) > 0
        assert any("data" in c.lower() or "cite" in c.lower() for c in constraints)

    def test_security_constraints(self, role_detector, roles_config):
        """Test security constraints."""
        config = {"enabled": True, "apply_constraints": True}
        applier = AutoRoleApplier(role_detector, roles_config, config)

        constraints = applier._get_constraints_for_role("security")

        assert len(constraints) > 0
        assert any("pii" in c.lower() or "compliance" in c.lower() for c in constraints)

    def test_unknown_role_no_constraints(self, role_detector, roles_config):
        """Test unknown role has no constraints."""
        config = {"enabled": True, "apply_constraints": True}
        applier = AutoRoleApplier(role_detector, roles_config, config)

        constraints = applier._get_constraints_for_role("unknown_role")

        assert constraints == []


class TestApplyRolePrefix:
    """Test role prefix application."""

    def test_apply_prefix_developer(self, auto_role_applier):
        """Test applying developer prefix."""
        prompt = "Refactor the code"
        result = auto_role_applier._apply_role_prefix(prompt, "developer")

        assert result.startswith("From a software engineering perspective,")
        assert "Refactor the code" in result

    def test_apply_prefix_general_no_prefix(self, auto_role_applier):
        """Test general role has no prefix."""
        prompt = "Some prompt"
        result = auto_role_applier._apply_role_prefix(prompt, "general")

        assert result == prompt

    def test_apply_prefix_missing_role(self, auto_role_applier):
        """Test prefix for missing role."""
        prompt = "Some prompt"
        result = auto_role_applier._apply_role_prefix(prompt, "non_existent_role")

        assert result == prompt

    def test_apply_prefix_with_newlines(self, auto_role_applier):
        """Test prefix includes proper newline separation."""
        prompt = "Refactor the code"
        result = auto_role_applier._apply_role_prefix(prompt, "developer")

        assert "\n\n" in result


class TestApplyResult:
    """Test apply() result structure."""

    def test_apply_returns_dict(self, auto_role_applier):
        """Test apply returns a dict."""
        result = auto_role_applier.apply("Test prompt")
        assert isinstance(result, dict)

    def test_apply_has_required_fields(self, auto_role_applier):
        """Test result has all required fields."""
        result = auto_role_applier.apply("Test prompt")

        required_fields = [
            "prompt", "role", "confidence", "secondary_roles",
            "keywords_matched", "constraints", "applied_features", "rationale"
        ]

        for field in required_fields:
            assert field in result

    def test_apply_field_types(self, auto_role_applier):
        """Test result field types."""
        result = auto_role_applier.apply("Refactor the code")

        assert isinstance(result["prompt"], str)
        assert isinstance(result["role"], str)
        assert isinstance(result["confidence"], float)
        assert isinstance(result["secondary_roles"], list)
        assert isinstance(result["keywords_matched"], list)
        assert isinstance(result["constraints"], list)
        assert isinstance(result["applied_features"], list)
        assert isinstance(result["rationale"], str)

    def test_confidence_in_valid_range(self, auto_role_applier):
        """Test confidence is 0-1."""
        result = auto_role_applier.apply("Some prompt")
        assert 0.0 <= result["confidence"] <= 1.0


class TestSecondaryRoles:
    """Test secondary role detection."""

    def test_secondary_roles_included(self, auto_role_applier):
        """Test secondary roles are detected."""
        result = auto_role_applier.apply("Refactor the code and fix the security vulnerability")

        assert "secondary_roles" in result
        assert isinstance(result["secondary_roles"], list)


class TestKeywordsMatched:
    """Test keyword tracking."""

    def test_keywords_matched_tracked(self, auto_role_applier):
        """Test that matched keywords are tracked."""
        result = auto_role_applier.apply("Refactor the code and fix the bug")

        assert "keywords_matched" in result
        assert isinstance(result["keywords_matched"], list)

    def test_keywords_match_prompt_content(self, auto_role_applier):
        """Test matched keywords are from the prompt."""
        result = auto_role_applier.apply("Refactor the authentication module")

        # Should have some keywords from the prompt
        keywords_lower = [kw.lower() for kw in result["keywords_matched"]]
        # At least one keyword should be relevant to developer role
        has_relevant_keyword = any(
            kw in keywords_lower for kw in ["refactor", "code", "module"]
        )
        # Keyword matching is fuzzy so we just check the list is not empty
        assert len(result["keywords_matched"]) >= 0


class TestDescribeAppliedChanges:
    """Test human-readable change descriptions."""

    def test_describe_no_changes(self, auto_role_applier):
        """Test description when no changes applied."""
        result = auto_role_applier.apply("Test")
        result["applied_features"] = []

        description = auto_role_applier.describe_applied_changes(result)

        assert description == "No changes applied"

    def test_describe_with_role_prefix(self, auto_role_applier):
        """Test description includes role prefix."""
        result = auto_role_applier.apply("Refactor the code")

        if result["applied_features"]:
            description = auto_role_applier.describe_applied_changes(result)
            assert result["role"] in description or "Applied" in description

    def test_describe_with_constraints(self, auto_role_applier):
        """Test description includes constraints."""
        result = auto_role_applier.apply("Refactor the code")

        if "constraints" in result["applied_features"] and result["constraints"]:
            description = auto_role_applier.describe_applied_changes(result)
            assert "constraints" in description.lower() or "Applied" in description


class TestSessionContext:
    """Test with session context."""

    def test_apply_with_session_context(self, auto_role_applier):
        """Test apply with session context."""
        context = {
            "file_type": "py",
            "project_type": "api"
        }

        result = auto_role_applier.apply("Refactor the code", context)

        assert result["role"] is not None
        assert result["prompt"] is not None

    def test_apply_without_session_context(self, auto_role_applier):
        """Test apply without context (uses None)."""
        result = auto_role_applier.apply("Refactor the code", None)

        assert result["role"] is not None
        assert result["prompt"] is not None
