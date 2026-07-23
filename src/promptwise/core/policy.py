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


def _merge_tighten(parent: "Policy", child: "Policy") -> "Policy":
    """Merge a parent (org/team) policy with a child (team/project) policy so
    the child can only tighten enforcement, never loosen it:
      * banned_operations / required_gates -- union (child adds, never removes).
      * allowed_model_tiers -- intersection when both set; child inherits the
        parent's list verbatim when it doesn't set its own.
      * budget_cap_usd -- the lower (tighter) of the two when both set.
    """
    if child.allowed_model_tiers and parent.allowed_model_tiers:
        allowed = [t for t in child.allowed_model_tiers if t in set(parent.allowed_model_tiers)]
        if not allowed:
            # An empty allowed_model_tiers means "no restriction" elsewhere in
            # this dataclass, so a disjoint child/parent intersection must
            # never collapse to that value here -- it would silently loosen
            # the merged policy to "allow every tier", the opposite of
            # tighten-only. Reject the config instead of guessing.
            raise ValueError(
                "policy extends: child allowed_model_tiers "
                f"{child.allowed_model_tiers} share no tiers with parent's "
                f"{parent.allowed_model_tiers} -- child must narrow the "
                "parent's list, not replace it with an unrelated one")
    else:
        allowed = child.allowed_model_tiers or parent.allowed_model_tiers

    if parent.budget_cap_usd is not None and child.budget_cap_usd is not None:
        budget_cap = min(parent.budget_cap_usd, child.budget_cap_usd)
    else:
        budget_cap = child.budget_cap_usd if child.budget_cap_usd is not None else parent.budget_cap_usd

    banned = sorted(set(parent.banned_operations) | set(child.banned_operations))
    gates = sorted(set(parent.required_gates) | set(child.required_gates))

    return Policy(
        budget_cap_usd=budget_cap,
        allowed_model_tiers=allowed,
        banned_operations=banned,
        required_gates=gates,
        raw={"parent": parent.raw, "child": child.raw},
    )


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
        """Load a policy file, optionally resolving an ``extends:`` chain
        (org -> team -> project inheritance). ``extends`` is resolved
        relative to the file that declares it. No ``extends`` key -> single-
        tier behavior is unchanged from before this feature existed --
        existing single-project policy files see no difference."""
        return cls._load_chain(Path(path), set())

    @classmethod
    def _load_chain(cls, path: Path, visited: set) -> "Policy":
        if yaml is None:  # pragma: no cover
            raise RuntimeError("PyYAML not available")
        resolved = path.resolve()
        if resolved in visited:
            raise ValueError(f"policy extends cycle detected at {path}")
        visited = visited | {resolved}

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        child = cls.from_dict(data)
        extends = data.get("extends")
        if not extends:
            return child

        parent_path = Path(extends)
        if not parent_path.is_absolute():
            parent_path = (path.parent / parent_path)
        parent = cls._load_chain(parent_path, visited)
        return _merge_tighten(parent, child)

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
