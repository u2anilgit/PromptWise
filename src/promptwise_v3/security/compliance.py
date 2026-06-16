import re
import yaml
from pathlib import Path


class ComplianceEngine:
    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir
        self._profiles: dict[str, dict] = {}

    def load_profile(self, name: str, path: Path | None = None) -> None:
        paths_to_try = [
            path,
            self.config_dir / f"{name}.yaml" if self.config_dir else None,
            Path("config") / "compliance" / f"{name}.yaml",
            Path(f"config/{name}.yaml"),
        ]
        for p in paths_to_try:
            if p and p.exists():
                try:
                    data = yaml.safe_load(p.read_text(encoding="utf-8"))
                    if data:
                        self._profiles[name] = data
                except Exception:
                    pass

    def check(self, text: str, profile_name: str) -> tuple[list[dict], str]:
        violations = []
        redacted = text
        profile = self._profiles.get(profile_name)
        if not profile:
            return violations, redacted

        for rule in profile.get("rules", []):
            try:
                pat = re.compile(rule["pattern"], re.I)
                if pat.search(redacted):
                    violations.append({"check": "compliance", "rule": rule.get("name", "unknown"),
                                       "detail": f"Violation: {rule.get('name', rule['pattern'])}"})
                    if rule.get("action") == "redact":
                        redacted = pat.sub("[REDACTED]", redacted)
            except re.error:
                pass

        return violations, redacted

    def get_loaded_profiles(self) -> list[str]:
        return list(self._profiles.keys())
