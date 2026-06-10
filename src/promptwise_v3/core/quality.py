from promptwise_v3.types import QualityResult


class QualityGuard:
    def __init__(self, confidence_threshold: float = 0.6, enabled: bool = True):
        self.confidence_threshold = confidence_threshold
        self.enabled = enabled

    def check(self, output: str | dict, skill_name: str = "") -> QualityResult:
        if not self.enabled:
            return QualityResult(score=1.0, passed=True, signals=[])

        signals: list[str] = []
        text = str(output) if isinstance(output, dict) else (output if output is not None else "")
        is_dict = isinstance(output, dict)

        if not text.strip():
            signals.append("empty_output")

        refusal_phrases = ("i cannot", "i don't know", "i'm not sure")
        if any(p in text.lower() for p in refusal_phrases):
            signals.append("refusal_signal")

        incomplete_markers = ("todo", "fixme", "[placeholder]", "...")
        if any(m.lower() in text.lower() for m in incomplete_markers):
            signals.append("incomplete_output")

        if is_dict and isinstance(output, dict):
            required = _required_fields(skill_name)
            if required and not all(f in output for f in required):
                signals.append("missing_required_fields")

        text_lower = text.lower()
        if "success" in text_lower and "failed" in text_lower:
            signals.append("contradictory_output")

        score = max(0.0, 1.0 - 0.15 * len(signals))
        passed = score >= self.confidence_threshold
        return QualityResult(score=score, passed=passed, signals=signals)


def _required_fields(skill_name: str) -> list[str]:
    mapping = {
        "summarize": ["summary"],
        "review": ["verdict", "comments"],
        "route_request": ["model", "reason"],
        "detect_role": ["role"],
        "validate_output": ["valid", "errors"],
    }
    return mapping.get(skill_name.lower(), [])
