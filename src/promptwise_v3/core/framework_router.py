"""Framework router — classify a task and recommend the right agentic-dev framework.

PromptWise's differentiator (see docs/index.html, section 03): instead of becoming
"framework #10", it classifies intent + scale + risk and routes the task to the best
existing open-source framework, then runs it through the role / compliance / context
engines. This module does the *recommendation*. Live subprocess wrapping of BMAD /
Spec Kit is intentionally out of scope for v1.0 (documented as roadmap).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FrameworkRecommendation:
    framework: str
    reason: str
    alternatives: list[str] = field(default_factory=list)
    artifact_chain: list[str] = field(default_factory=list)
    compliance_gate: bool = False
    signals: dict = field(default_factory=dict)


# Catalogue — name, what it is, license, the artifact chain it produces.
_FRAMEWORKS = {
    "spec-kit": {
        "label": "GitHub Spec Kit",
        "chain": ["constitution", "spec", "plan", "tasks", "implement"],
        "note": "Spec-driven; its constitution.md is the compliance activation point.",
    },
    "bmad": {
        "label": "BMAD-METHOD",
        "chain": ["analyst", "prd", "architecture", "stories", "dev", "qa"],
        "note": "12+ agent personas across the full SDLC; seeds the 14 role packs.",
    },
    "openspec": {
        "label": "OpenSpec",
        "chain": ["proposal", "change-spec", "review", "apply"],
        "note": "Change-gated workflow for brownfield edits.",
    },
    "taskmaster": {
        "label": "TaskMaster",
        "chain": ["prd", "dependency-graph", "tasks"],
        "note": "PRD -> dependency-aware tasks over MCP.",
    },
    "kiro-hooks": {
        "label": "Kiro-style agent hooks",
        "chain": ["event", "hook", "action"],
        "note": "Event-driven, save-triggered automation via the plugin layer.",
    },
}

_REGULATED = re.compile(
    r"\b(hipaa|phi|hl7|fhir|banking|finra|basel|pci|aml|gdpr|sox|soc\s?2|audit|regulat|compliance|legal)\b",
    re.I,
)
_BROWNFIELD = re.compile(
    r"\b(refactor|migrat|legacy|existing|brownfield|change request|patch|bug ?fix|modif(y|ied)|maintain)\b",
    re.I,
)
_MULTI_ROLE = re.compile(
    r"\b(full product|end[- ]to[- ]end|whole app|mvp|from scratch|team|multi[- ]role|product build|greenfield app)\b",
    re.I,
)
_PRD_ONLY = re.compile(
    r"\b(prd|break(down| into)? tasks|task list|backlog|user stor(y|ies)|sprint|tickets?)\b",
    re.I,
)
_HOOK = re.compile(
    r"\b(on save|save[- ]trigger|when .* changes|automat(e|ion)|watch|hook|pre[- ]commit|post[- ]commit)\b",
    re.I,
)


class FrameworkRouter:
    """Classify a task description and recommend an agentic-dev framework."""

    def recommend(
        self,
        text: str,
        regulated: bool | None = None,
        brownfield: bool | None = None,
    ) -> FrameworkRecommendation:
        t = text or ""

        is_regulated = _REGULATED.search(t) is not None if regulated is None else regulated
        is_brownfield = _BROWNFIELD.search(t) is not None if brownfield is None else brownfield
        is_multi_role = _MULTI_ROLE.search(t) is not None
        is_prd_only = _PRD_ONLY.search(t) is not None
        is_hook = _HOOK.search(t) is not None

        signals = {
            "regulated": is_regulated,
            "brownfield": is_brownfield,
            "multi_role": is_multi_role,
            "prd_only": is_prd_only,
            "hook_driven": is_hook,
        }

        # Decision order mirrors docs/index.html section 03 (most-specific first).
        if is_hook:
            choice, reason = "kiro-hooks", "Save/event-triggered automation -> wire as plugin hooks."
        elif is_prd_only and not is_multi_role:
            choice, reason = "taskmaster", "Scope is PRD -> dependency-aware tasks only; no full SDLC needed."
        elif is_brownfield:
            choice, reason = "openspec", "Brownfield change -> use a change-gated spec workflow."
        elif is_regulated:
            choice, reason = "spec-kit", "Greenfield + regulated -> spec-driven with a constitution as the compliance gate."
        elif is_multi_role:
            choice, reason = "bmad", "Full multi-role product build -> persona-driven SDLC; seeds the role packs."
        else:
            choice, reason = "spec-kit", "Default: spec-driven keeps an auditable artifact chain at low overhead."

        fw = _FRAMEWORKS[choice]
        alternatives = [k for k in ("spec-kit", "bmad", "openspec", "taskmaster") if k != choice][:2]

        return FrameworkRecommendation(
            framework=fw["label"],
            reason=f"{reason} {fw['note']}",
            alternatives=[_FRAMEWORKS[a]["label"] for a in alternatives],
            artifact_chain=fw["chain"],
            compliance_gate=is_regulated,
            signals=signals,
        )
