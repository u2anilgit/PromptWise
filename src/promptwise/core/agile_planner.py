"""agile_planner — two-phase, persona-aware plan layered on WorkflowPlanner.

Reuses WorkflowPlanner's greenfield/brownfield/regulated classification and its
compliance graft, then shapes the result into the agile method's two phases:

    planning phase (expensive tier):  analyst -> pm -> [ux] -> architect -> po
    dev loop (cheap tier, per story): sm -> dev -> qa(gate)

The regulated path is preserved, never bypassed: when the base plan flags
compliance, security-architecture is injected into planning and owasp_scan +
get_sbom into the dev loop, and the compliance rules ride into each story.

Import-defensive: a differing/absent WorkflowPlanner degrades gracefully rather
than crashing. Config is read from config/agile.yaml when present, else defaults.
Stdlib + optional PyYAML. No network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:  # reuse the existing classifier when available
    from promptwise.core.workflow_planner import WorkflowPlanner
except Exception:  # pragma: no cover - degrade gracefully
    WorkflowPlanner = None  # type: ignore

try:  # PyYAML is already a PromptWise dependency
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


_DEFAULTS = {
    "planning_order": ["agile-analyst", "agile-pm", "agile-ux", "agile-architect", "agile-po"],
    "dev_loop": ["agile-sm", "agile-dev", "agile-qa"],
    "model_tiers": {"planning": "opus", "execution": "sonnet"},
    "effort_tiers": {"planning": "high", "execution": "medium"},
    "regulated_inject": {
        "planning": ["security-architecture"],
        "dev_loop_tools": ["owasp_scan", "get_sbom"],
    },
}

# persona pack -> phase label (purely cosmetic, for the plan output)
_PHASE_LABEL = {
    "agile-analyst": "discovery", "agile-pm": "prd", "agile-ux": "ux-spec",
    "agile-architect": "architecture", "agile-po": "shard-validate",
    "agile-sm": "draft-story", "agile-dev": "implement", "agile-qa": "quality-gate",
}


@dataclass
class AgileStep:
    phase: str          # "planning" | "development"
    persona: str        # the agile persona pack, e.g. "agile-sm"
    skill: str          # same as persona (the pack that runs)
    model_tier: str     # "opus" planning / "sonnet" execution
    effort: str = "medium"   # "low" | "medium" | "high" -- independent of model_tier
    label: str = ""     # cosmetic phase label

    def to_dict(self) -> dict:
        return {"phase": self.phase, "persona": self.persona, "skill": self.skill,
                "model_tier": self.model_tier, "effort": self.effort, "label": self.label}


@dataclass
class AgilePlan:
    workflow: str
    reason: str
    planning: list[AgileStep] = field(default_factory=list)
    dev_loop: list[AgileStep] = field(default_factory=list)
    inject_tools: list[str] = field(default_factory=list)   # regulated graft for the dev loop
    compliance_gate: bool = False
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "workflow": self.workflow,
            "reason": self.reason,
            "planning": [s.to_dict() for s in self.planning],
            "dev_loop": [s.to_dict() for s in self.dev_loop],
            "inject_tools": list(self.inject_tools),
            "compliance_gate": self.compliance_gate,
            "signals": self.signals,
        }


def _load_config(config_path: str | Path | None) -> dict:
    cfg = dict(_DEFAULTS)
    if not config_path or yaml is None:
        return cfg
    p = Path(config_path)
    if not p.exists():
        return cfg
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:  # pragma: no cover - bad yaml -> defaults
        return cfg
    for k in ("planning_order", "dev_loop", "model_tiers", "effort_tiers", "regulated_inject"):
        if data.get(k):
            cfg[k] = data[k]
    return cfg


class AgilePlanner:
    """Produce the two-phase persona plan, reusing WorkflowPlanner classification."""

    def __init__(self, config_path: str | Path | None = "config/agile.yaml"):
        self.cfg = _load_config(config_path)
        self._wp = WorkflowPlanner() if WorkflowPlanner is not None else None

    def _classify(self, text: str, regulated: bool | None, brownfield: bool | None):
        """Return (workflow, reason, compliance_gate, signals) reusing WorkflowPlanner."""
        if self._wp is not None:
            base = self._wp.plan(text, regulated, brownfield)
            return base.workflow, base.reason, base.compliance_gate, dict(base.signals)
        # Defensive fallback: minimal local classification.
        comp = bool(regulated)
        return ("agile-build", "WorkflowPlanner unavailable — agile plan only.", comp,
                {"regulated": comp, "brownfield": bool(brownfield)})

    def plan(self, text: str, regulated: bool | None = None,
             brownfield: bool | None = None) -> AgilePlan:
        workflow, reason, compliance_gate, signals = self._classify(text, regulated, brownfield)

        plan_tier = self.cfg["model_tiers"].get("planning", "opus")
        exec_tier = self.cfg["model_tiers"].get("execution", "sonnet")
        plan_effort = self.cfg.get("effort_tiers", {}).get("planning", "high")
        exec_effort = self.cfg.get("effort_tiers", {}).get("execution", "medium")

        planning_order = list(self.cfg["planning_order"])
        # Regulated: inject security personas/packs into the planning phase.
        if compliance_gate:
            inject = self.cfg.get("regulated_inject", {}).get("planning", [])
            # place security design right after architecture if present, else append
            if "agile-architect" in planning_order:
                idx = planning_order.index("agile-architect") + 1
                for j, pack in enumerate(inject):
                    planning_order.insert(idx + j, pack)
            else:
                planning_order.extend(inject)

        planning = [
            AgileStep(phase="planning", persona=p, skill=p, model_tier=plan_tier, effort=plan_effort,
                      label=_PHASE_LABEL.get(p, "planning"))
            for p in planning_order
        ]
        dev_loop = [
            AgileStep(phase="development", persona=p, skill=p, model_tier=exec_tier, effort=exec_effort,
                      label=_PHASE_LABEL.get(p, "development"))
            for p in self.cfg["dev_loop"]
        ]

        inject_tools = []
        if compliance_gate:
            inject_tools = list(self.cfg.get("regulated_inject", {}).get("dev_loop_tools", []))
            reason += " Regulated — security packs in planning; owasp_scan + get_sbom + compliance rules in the dev loop."

        return AgilePlan(
            workflow=f"agile:{workflow}",
            reason=reason,
            planning=planning,
            dev_loop=dev_loop,
            inject_tools=inject_tools,
            compliance_gate=compliance_gate,
            signals=signals,
        )
