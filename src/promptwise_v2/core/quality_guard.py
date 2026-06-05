from dataclasses import dataclass, field


@dataclass
class QualityResult:
    score: float          # 0.0 to 1.0
    passed: bool          # score >= threshold
    signals: list[str]    # detected issues (empty = clean)


class QualityGuard:
    def __init__(self, confidence_threshold: float = 0.6, enabled: bool = True):
        self.confidence_threshold = confidence_threshold
        self.enabled = enabled

    def check(self, output: "str | dict", skill_name: str = "") -> QualityResult:
        """
        Run hallucination / quality signal checks on an output.

        If not enabled: return QualityResult(score=1.0, passed=True, signals=[])

        Hallucination signal checks (each hit reduces score by 0.15):
        1. Empty output                  → signal "empty_output"
        2. "I cannot" / "I don't know" / "I'm not sure"
                                         → signal "refusal_signal"
        3. "TODO" / "FIXME" / "[placeholder]" / "..."
                                         → signal "incomplete_output"
        4. dict with missing required fields (derived from skill_name context)
                                         → signal "missing_required_fields"
        5. Contains both "success" and "failed" (case-insensitive)
                                         → signal "contradictory_output"

        score  = max(0.0, 1.0 - 0.15 * len(signals))
        passed = score >= confidence_threshold
        """
        if not self.enabled:
            return QualityResult(score=1.0, passed=True, signals=[])

        signals: list[str] = []

        # Normalise to string for most checks
        if isinstance(output, dict):
            text = str(output)
            is_dict = True
        else:
            text = output if output is not None else ""
            is_dict = False

        # 1. Empty output
        if not text.strip():
            signals.append("empty_output")

        # 2. Refusal / uncertainty markers
        refusal_phrases = ("I cannot", "I don't know", "I'm not sure")
        if any(phrase.lower() in text.lower() for phrase in refusal_phrases):
            signals.append("refusal_signal")

        # 3. Incomplete / placeholder markers
        incomplete_markers = ("TODO", "FIXME", "[placeholder]", "...")
        if any(marker.lower() in text.lower() for marker in incomplete_markers):
            signals.append("incomplete_output")

        # 4. Missing required fields (only meaningful for dict output)
        if is_dict and isinstance(output, dict):
            # Infer required fields from skill_name heuristics (e.g. "summarize" → ["summary"])
            required_fields = _infer_required_fields(skill_name)
            if required_fields and not all(f in output for f in required_fields):
                signals.append("missing_required_fields")

        # 5. Contradictory output
        text_lower = text.lower()
        if "success" in text_lower and "failed" in text_lower:
            signals.append("contradictory_output")

        score = max(0.0, 1.0 - 0.15 * len(signals))
        passed = score >= self.confidence_threshold
        return QualityResult(score=score, passed=passed, signals=signals)


def _infer_required_fields(skill_name: str) -> list[str]:
    """
    Return a list of field names that are expected for the given skill.
    This is a lightweight heuristic; richer schemas live in Skill.output_schema.
    """
    _skill_fields: dict[str, list[str]] = {
        "summarize": ["summary"],
        "review": ["verdict", "comments"],
        "route_request": ["model", "reason"],
        "detect_role": ["role"],
        "validate_output": ["valid", "errors"],
    }
    return _skill_fields.get(skill_name.lower(), [])
