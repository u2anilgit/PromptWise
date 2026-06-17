"""policy — cross-agent policy-as-code (the neutral runtime constitution).

Evaluate a proposed action (model tier, cost, operation, gates) against a single
policy and return an allow/block decision with recorded reasons. Stdlib + PyYAML
(already a PromptWise dependency). No network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # PyYAML is already used by skill_loader.py
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


@dataclass
class PolicyDecision:
    allowed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "violations": list(self.violations), "warnings": list(self.warnings)}


@dataclass
class Policy:
    budget_cap_usd: float | None = None
    allowed_model_tiers: list[str] = field(default_factory=list)   # empty = allow all
    banned_operations: list[str] = field(default_factory=list)
    required_gates: list[str] = field(default_factory=list)         # e.g. ["quality", "compliance"]
    raw: dict = field(default_factory=dict)

    # ---- loaders ----
    @classmethod
    def from_dict(cls, d: dict | None) -> "Policy":
        d = d or {}
        return cls(
            budget_cap_usd=d.get("budget_cap_usd"),
            allowed_model_tiers=[str(t).lower() for t in d.get("allowed_model_tiers", []) or []],
            banned_operations=[str(o).lower() for o in d.get("banned_operations", []) or []],
            required_gates=[str(g).lower() for g in d.get("required_gates", []) or []],
            raw=d,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Policy":
        if yaml is None:  # pragma: no cover
            raise RuntimeError("PyYAML not available")
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_dict(data)

    # ---- evaluation ----
    def evaluate_action(
        self,
        *,
        model_tier: str | None = None,
        estimated_cost: float | None = None,
        spent_so_far: float | None = None,
        operation: str | None = None,
        gates_passed: list[str] | None = None,
    ) -> PolicyDecision:
        violations: list[str] = []
        warnings: list[str] = []

        if self.allowed_model_tiers and model_tier is not None:
            if model_tier.lower() not in self.allowed_model_tiers:
                violations.append(
                    f"model tier '{model_tier}' not in allowed {self.allowed_model_tiers}"
                )

        if self.budget_cap_usd is not None:
            spent = float(spent_so_far or 0.0)
            cost = float(estimated_cost or 0.0)
            projected = spent + cost
            if projected > self.budget_cap_usd:
                violations.append(
                    f"budget cap exceeded: ${projected:.4f} > ${self.budget_cap_usd:.4f}"
                )
            elif self.budget_cap_usd and projected > 0.9 * self.budget_cap_usd:
                warnings.append(
                    f"approaching budget cap: ${projected:.4f} of ${self.budget_cap_usd:.4f}"
                )

        if operation is not None and operation.lower() in self.banned_operations:
            violations.append(f"operation '{operation}' is banned by policy")

        if self.required_gates:
            passed = {g.lower() for g in (gates_passed or [])}
            missing = [g for g in self.required_gates if g not in passed]
            if missing:
                violations.append(f"required gate(s) not passed: {missing}")

        return PolicyDecision(allowed=not violations, violations=violations, warnings=warnings)
