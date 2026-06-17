"""quality_gate — advisory quality gate decision (PASS / CONCERNS / FAIL / WAIVED).

Deterministic, auditable, stdlib only. Composes the *findings* produced by the
existing review/test/threat packs into a single recorded decision.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

PASS = "PASS"
CONCERNS = "CONCERNS"
FAIL = "FAIL"
WAIVED = "WAIVED"
DECISIONS = (PASS, CONCERNS, FAIL, WAIVED)

_HIGH = {"high", "critical", "blocker"}
_MED = {"medium", "moderate"}


@dataclass
class GateResult:
    story_id: str
    decision: str
    risk_score: int = 0
    findings: list[dict] = field(default_factory=list)
    nfr_assessment: dict = field(default_factory=dict)
    waiver_reason: str = ""
    reviewed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "story_id": self.story_id,
            "decision": self.decision,
            "risk_score": self.risk_score,
            "findings": list(self.findings),
            "nfr_assessment": dict(self.nfr_assessment),
            "waiver_reason": self.waiver_reason,
            "reviewed_at": self.reviewed_at,
        }


class QualityGate:
    """Decision rules (in order):

    1. If an unresolved high/critical finding exists:
         - WAIVED if a non-empty waiver_reason is supplied (recorded for audit)
         - else FAIL
    2. Else if any medium finding OR risk_score >= concerns_threshold: CONCERNS
    3. Else: PASS
    """

    def __init__(self, concerns_threshold: int = 40, fail_on_high: bool = True):
        self.concerns_threshold = concerns_threshold
        self.fail_on_high = fail_on_high

    @staticmethod
    def _sev(f: dict) -> str:
        return str(f.get("severity", "")).strip().lower()

    def evaluate(
        self,
        story_id: str,
        findings: list[dict] | None = None,
        risk_score: int = 0,
        nfr_assessment: dict | None = None,
        waiver_reason: str = "",
    ) -> GateResult:
        findings = findings or []
        has_high = any(self._sev(f) in _HIGH for f in findings)
        has_med = any(self._sev(f) in _MED for f in findings)

        if has_high and self.fail_on_high:
            decision = WAIVED if waiver_reason.strip() else FAIL
        elif has_med or risk_score >= self.concerns_threshold:
            decision = CONCERNS
        else:
            decision = PASS

        return GateResult(
            story_id=story_id,
            decision=decision,
            risk_score=int(risk_score),
            findings=findings,
            nfr_assessment=nfr_assessment or {},
            waiver_reason=waiver_reason if decision == WAIVED else "",
            reviewed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
