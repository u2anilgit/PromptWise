"""
Apply auto-detected roles to prompts.

Takes detected role + config and applies role-specific prefixes and constraints.
"""

from typing import Dict, Any, List, Optional

from .role_detector import RoleDetector, RoleDetectionResult


class AutoRoleApplier:
    """
    Apply auto-detected roles to prompts.

    Pipeline:
    1. Detect role from prompt context
    2. Check confidence threshold
    3. Apply role-specific prefix
    4. Apply role-specific constraints
    """

    def __init__(
        self,
        role_detector: RoleDetector,
        roles_config: Dict[str, Dict],
        auto_role_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize applier.

        Args:
            role_detector: RoleDetector instance
            roles_config: Role definitions with prefixes (from roles.yaml)
            auto_role_config: {
                'enabled': bool (default True),
                'confidence_threshold': float (default 0.65),
                'apply_constraints': bool (default True)
            }
        """
        self.detector = role_detector
        self.roles_config = roles_config
        self.auto_role_config = auto_role_config or {}
        self.enabled = self.auto_role_config.get("enabled", True)
        self.confidence_threshold = self.auto_role_config.get("confidence_threshold", 0.65)
        self.apply_constraints = self.auto_role_config.get("apply_constraints", True)

    def apply(self, prompt: str, session_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Apply auto-detected role to prompt.

        Args:
            prompt: User prompt text
            session_context: Optional context (file_type, project_type, etc.)

        Returns:
            {
                'prompt': <modified prompt with prefix>,
                'role': <detected role name>,
                'confidence': <0.0-1.0>,
                'secondary_roles': [(<role>, <confidence>), ...],
                'keywords_matched': [<keyword>, ...],
                'constraints': [<constraint>, ...],
                'applied_features': [<feature name>, ...],
                'rationale': <explanation>
            }
        """
        session_context = session_context or {}

        if not self.enabled:
            return {
                "prompt": prompt,
                "role": "general",
                "confidence": 0.0,
                "secondary_roles": [],
                "keywords_matched": [],
                "constraints": [],
                "applied_features": [],
                "rationale": "Auto-role detection disabled"
            }

        # Step 1: Detect role
        detection = self.detector.detect(prompt, context=session_context)

        # Step 2: Check confidence threshold
        if detection.confidence < self.confidence_threshold:
            return {
                "prompt": prompt,
                "role": "general",
                "confidence": detection.confidence,
                "secondary_roles": detection.secondary_roles,
                "keywords_matched": detection.keywords_matched,
                "constraints": [],
                "applied_features": [],
                "rationale": f"Confidence {detection.confidence:.2f} below threshold {self.confidence_threshold}; using general role"
            }

        # Step 3: Apply role prefix
        modified_prompt = self._apply_role_prefix(prompt, detection.primary_role)
        applied_features = ["role_prefix"]

        # Step 4: Apply role-specific constraints
        constraints = []
        if self.apply_constraints:
            constraints = self._get_constraints_for_role(detection.primary_role)
            applied_features.append("constraints")

        return {
            "prompt": modified_prompt,
            "role": detection.primary_role,
            "confidence": detection.confidence,
            "secondary_roles": detection.secondary_roles,
            "keywords_matched": detection.keywords_matched,
            "constraints": constraints,
            "applied_features": applied_features,
            "rationale": detection.rationale
        }

    def _apply_role_prefix(self, prompt: str, role: str) -> str:
        """
        Prepend role-specific prefix to prompt.

        Args:
            prompt: Original prompt
            role: Role name

        Returns:
            Modified prompt
        """
        if role not in self.roles_config:
            return prompt

        role_def = self.roles_config[role]
        prefix = role_def.get("prefix")

        if prefix:
            return f"{prefix}\n\n{prompt}"

        return prompt

    def _get_constraints_for_role(self, role: str) -> List[str]:
        """
        Get role-specific workflow constraints.

        Args:
            role: Role name

        Returns:
            List of constraint names
        """
        constraints_map = {
            "developer": [
                "prefer_code_blocks",
                "include_imports",
                "validate_syntax",
                "show_example_usage"
            ],
            "analyst": [
                "include_sample_data",
                "cite_sources",
                "show_formulas",
                "provide_confidence_intervals"
            ],
            "manager": [
                "summarize_action_items",
                "highlight_risks",
                "estimate_effort",
                "suggest_timeline"
            ],
            "security": [
                "flag_pii",
                "check_compliance",
                "mention_cve",
                "suggest_mitigations"
            ],
            "IT": [
                "specify_versions",
                "include_deployment_steps",
                "document_dependencies",
                "suggest_monitoring"
            ],
            "designer": [
                "consider_accessibility",
                "describe_user_flow",
                "suggest_color_palette",
                "mention_responsive_design"
            ],
            "writer": [
                "maintain_narrative_flow",
                "use_consistent_tone",
                "add_transitions",
                "proofread"
            ],
            "researcher": [
                "cite_sources",
                "link_to_papers",
                "mention_limitations",
                "suggest_future_work"
            ],
            "pm": [
                "include_acceptance_criteria",
                "identify_stakeholders",
                "estimate_effort",
                "suggest_success_metrics"
            ],
            "legal": [
                "check_regulatory_compliance",
                "flag_liability_risks",
                "suggest_legal_review",
                "include_disclaimers"
            ],
            "healthcare": [
                "verify_hipaa_compliance",
                "cite_clinical_guidelines",
                "flag_patient_safety_risks",
                "suggest_fhir_format"
            ],
            "finance": [
                "check_regulatory_compliance",
                "flag_audit_trails",
                "suggest_reconciliation",
                "mention_aml_risk"
            ],
            "data": [
                "optimize_query_performance",
                "suggest_indexing",
                "consider_data_volume",
                "mention_schema_design"
            ],
            "qassurance": [
                "define_test_scope",
                "suggest_automation_framework",
                "identify_edge_cases",
                "recommend_coverage_target"
            ],
            "executive": [
                "focus_on_roi",
                "highlight_competitive_advantage",
                "include_financial_impact",
                "suggest_risk_mitigation"
            ]
        }

        return constraints_map.get(role, [])

    def describe_applied_changes(self, result: Dict[str, Any]) -> str:
        """
        Generate human-readable description of applied changes.

        Args:
            result: Result from apply()

        Returns:
            Description string
        """
        if not result["applied_features"]:
            return "No changes applied"

        role = result["role"]
        confidence = result["confidence"]
        features = result["applied_features"]

        desc_parts = [f"Applied {role} role ({confidence:.0%} confidence)"]

        if "role_prefix" in features:
            desc_parts.append(f"  • Added role prefix")

        if "constraints" in features and result["constraints"]:
            num_constraints = len(result["constraints"])
            desc_parts.append(f"  • Applied {num_constraints} constraints")

        if result["secondary_roles"]:
            secondaries = ", ".join(r for r, _ in result["secondary_roles"][:2])
            desc_parts.append(f"  • Secondary roles detected: {secondaries}")

        return "\n".join(desc_parts)


__all__ = ["AutoRoleApplier"]
