"""Workflow planner — map a task to an ordered chain of PromptWise's OWN skill packs.

Self-contained: every step is a PromptWise skill pack (in skill_packs/) or a built-in
MCP tool, runnable directly via `invoke_skill` / the server. No third-party frameworks,
no external CLIs, no network — PromptWise plans and runs the whole SDLC artifact chain
itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class WorkflowStep:
    phase: str
    skill: str          # skill pack name (skill_packs/) or built-in MCP tool
    kind: str           # "skill_pack" | "mcp_tool"


@dataclass
class WorkflowPlan:
    workflow: str
    reason: str
    steps: list[WorkflowStep] = field(default_factory=list)
    compliance_gate: bool = False
    signals: dict = field(default_factory=dict)


_REGULATED = re.compile(
    r"\b(hipaa|phi|hl7|fhir|banking|finra|basel|pci|aml|gdpr|sox|soc\s?2|audit|regulat|compliance|legal)\b",
    re.I,
)
_BROWNFIELD = re.compile(
    r"\b(refactor|migrat|legacy|existing|brownfield|change request|patch|bug ?fix|debug|modif(y|ied)|maintain)\b",
    re.I,
)
_GREENFIELD = re.compile(
    r"\b(build|new (app|feature|service|product)|from scratch|greenfield|mvp|prototype|implement)\b",
    re.I,
)
_DOCS_ONLY = re.compile(
    r"\b(prd|spec|user stor(y|ies)|requirements?|backlog|adr|design doc|documentation)\b",
    re.I,
)


def _s(skill: str) -> WorkflowStep:
    return WorkflowStep(phase="", skill=skill, kind="skill_pack")


def _t(tool: str) -> WorkflowStep:
    return WorkflowStep(phase="", skill=tool, kind="mcp_tool")


class WorkflowPlanner:
    """Classify a task and return a PromptWise-native skill-pack workflow."""

    def plan(
        self,
        text: str,
        regulated: bool | None = None,
        brownfield: bool | None = None,
    ) -> WorkflowPlan:
        t = text or ""

        is_regulated = _REGULATED.search(t) is not None if regulated is None else regulated
        is_brownfield = _BROWNFIELD.search(t) is not None if brownfield is None else brownfield
        is_greenfield = _GREENFIELD.search(t) is not None
        is_docs_only = _DOCS_ONLY.search(t) is not None and not is_greenfield

        signals = {
            "regulated": is_regulated,
            "brownfield": is_brownfield,
            "greenfield": is_greenfield,
            "docs_only": is_docs_only,
        }

        if is_docs_only:
            workflow = "spec"
            reason = "Documentation/spec task — produce the artifact chain only."
            phases = [
                ("detect-role", _t("detect_role")),
                ("prd", _s("prd-generator")),
                ("stories", _s("user-story-generator")),
                ("decision-record", _s("adr")),
            ]
        elif is_brownfield:
            workflow = "brownfield-change"
            reason = "Change to existing code — debug, refactor, review, verify."
            phases = [
                ("detect-role", _t("detect_role")),
                ("diagnose", _s("systematic-debugging")),
                ("refactor", _s("refactoring")),
                ("test", _s("test-generator")),
                ("review", _s("code-review")),
                ("verify", _s("verification-before-completion")),
            ]
        else:
            # Greenfield / default full build.
            workflow = "greenfield-build"
            reason = "New build — full PRD -> design -> stories -> TDD -> review chain."
            phases = [
                ("detect-role", _t("detect_role")),
                ("prd", _s("prd-generator")),
                ("architecture", _s("system-design")),
                ("stories", _s("user-story-generator")),
                ("dev", _s("tdd")),
                ("review", _s("code-review")),
                ("verify", _s("verification-before-completion")),
            ]

        # Regulated tasks get compliance/security packs grafted in.
        if is_regulated:
            workflow = f"{workflow}+compliance"
            reason += " Regulated context — added security-architecture + OWASP gate."
            phases = (
                phases[:1]
                + [("security-design", _s("security-architecture"))]
                + phases[1:]
                + [("owasp-gate", _t("owasp_scan")), ("sbom", _t("get_sbom"))]
            )

        steps = [WorkflowStep(phase=p, skill=s.skill, kind=s.kind) for p, s in phases]

        return WorkflowPlan(
            workflow=workflow,
            reason=reason,
            steps=steps,
            compliance_gate=is_regulated,
            signals=signals,
        )
