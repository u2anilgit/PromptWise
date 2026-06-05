import re
import urllib.request
import json
import yaml
from pathlib import Path
from promptwise_v2.types_v2 import SecurityResult

_CHECKS = ["syntax", "secrets", "destructive", "supply_chain", "permissions", "pii", "injection", "compliance"]

_SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|secret|password|token|sk-)[=:\s]["\']?[a-z0-9\-_]{8,}', re.I),
    re.compile(r'(?i)bearer\s+[a-z0-9\-_\.]{20,}'),
]

_DESTRUCTIVE_PATTERNS = [
    re.compile(r'\brm\s+-rf\b'),
    re.compile(r'\bdrop\s+table\b', re.I),
    re.compile(r'\bdelete\s+from\b', re.I),
    re.compile(r'\bformat\s+[a-z]:\b', re.I),
    re.compile(r'\btruncate\b', re.I),
]

_SUPPLY_CHAIN_PATTERNS = [
    re.compile(r'pip\s+install\s+.*http://', re.I),
    re.compile(r'npm\s+install\s+.*http://', re.I),
    re.compile(r'curl\s+.*\|\s*(bash|sh)\b', re.I),
    re.compile(r'wget\s+.*\|\s*(bash|sh)\b', re.I),
]

_PERMISSION_PATTERNS = [
    re.compile(r'\bsudo\b'),
    re.compile(r'\bchmod\s+[0-7]{3,4}\b'),
    re.compile(r'\bchown\s+root\b'),
    re.compile(r'\bsu\s+-\b'),
    re.compile(r'/etc/passwd'),
    re.compile(r'/etc/shadow'),
]

_PII_PATTERNS = [
    ("email", re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')),
    ("phone", re.compile(r'\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b')),
    ("ssn", re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
    ("credit_card", re.compile(r'\b(?:\d[ -]*?){13,16}\b')),
]

_INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(previous|prior|all)\s+instructions', re.I),
    re.compile(r'disregard\s+(your|all)\s+(instructions|rules)', re.I),
    re.compile(r'you\s+are\s+now\s+', re.I),
    re.compile(r'new\s+persona', re.I),
    re.compile(r'dan\s+mode|jailbreak', re.I),
]


class SecurityChecker:
    def __init__(self, config=None):
        self.config = config

    def check(self, text: str, role: str = None) -> SecurityResult:
        violations = []
        risk_score = 0.0
        redacted_text = text

        # Default role to configuration current if available
        if role is None and self.config:
            role = self.config.roles.current

        # 1. Syntax (ignore instructions / DAN patterns)
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(redacted_text):
                violations.append({"check": "syntax", "detail": pattern.pattern})
                risk_score += 0.4

        # 2. Secrets
        for pattern in _SECRET_PATTERNS:
            if pattern.search(redacted_text):
                violations.append({"check": "secrets", "detail": pattern.pattern})
                risk_score += 0.8

        # 3. Destructive
        for pattern in _DESTRUCTIVE_PATTERNS:
            if pattern.search(redacted_text):
                violations.append({"check": "destructive", "detail": pattern.pattern})
                risk_score += 0.7

        # 4. Supply Chain (legacy checks)
        for pattern in _SUPPLY_CHAIN_PATTERNS:
            if pattern.search(redacted_text):
                violations.append({"check": "supply_chain", "detail": pattern.pattern})
                risk_score += 0.9

        # OSV Supply Chain check
        pip_matches = re.findall(r'pip\s+install\s+([a-zA-Z0-9-_]+)==([0-9.]+)', redacted_text)
        for pkg, ver in pip_matches:
            osv_res = self.check_osv_vulnerability(pkg, ver)
            if osv_res and "vulns" in osv_res:
                violations.append({"check": "supply_chain", "detail": f"OSV vulnerability found in {pkg}=={ver}"})
                risk_score += 0.8

        # 5. Permissions
        for pattern in _PERMISSION_PATTERNS:
            if pattern.search(redacted_text):
                violations.append({"check": "permissions", "detail": pattern.pattern})
                risk_score += 0.6

        # 6. PII Detection (Level 6)
        if not self.config or self.config.compliance.pii_detection:
            pii_found = False
            for label, pattern in _PII_PATTERNS:
                if pattern.search(redacted_text):
                    violations.append({"check": "pii", "detail": f"Found PII: {label}"})
                    risk_score += 0.5
                    pii_found = True
                    if self.config and self.config.compliance.pii_action == "redact":
                        redacted_text = pattern.sub(f"[REDACTED_{label.upper()}]", redacted_text)
            
            if pii_found and self.config and self.config.compliance.pii_action == "block":
                risk_score = 1.0

        # 7. Prompt Injection Detector (Level 7)
        if not self.config or self.config.compliance.injection_detection:
            for pattern in _INJECTION_PATTERNS:
                if pattern.search(redacted_text):
                    violations.append({"check": "injection", "detail": f"Injection attempt: {pattern.pattern}"})
                    risk_score += 0.6

        # 8. Compliance Profiler (Level 8)
        risk_score, redacted_text = self._check_compliance(redacted_text, role, violations, risk_score)

        risk_score = min(1.0, risk_score)
        passed = len(violations) == 0
        blocked = risk_score >= 0.7

        checks_run = ["syntax", "secrets", "destructive", "supply_chain", "permissions"]
        if self.config:
            checks_run.extend(["pii", "injection", "compliance"])

        return SecurityResult(
            passed=passed,
            checks_run=checks_run,
            violations=violations,
            risk_score=round(risk_score, 3),
            blocked=blocked,
            details=f"{len(violations)} violation(s) found" if violations else "clean",
        )

    def check_owasp(self, code: str) -> list[dict]:
        vulns = []
        # A03:2021-Injection (SQL Injection)
        if re.search(r"(execute|query)\s*\(\s*(f['\"].*?\{|['\"].*?\s*\+\s*\w+)", code, re.I):
            vulns.append({
                "vuln": "A03:2021-Injection (SQL Injection)",
                "severity": "HIGH",
                "detail": "Detect raw string concatenation or interpolation in SQL execution. Use parameterized queries."
            })
        # A03:2021-Injection (Command Injection)
        if re.search(r"\b(os\.system|subprocess\.Popen|subprocess\.run|eval|exec)\b", code):
            vulns.append({
                "vuln": "A03:2021-Injection (Command Injection)",
                "severity": "HIGH",
                "detail": "Avoid executing OS command strings or using eval/exec on untrusted input."
            })
        # A05:2021-Security Misconfiguration
        if re.search(r"ssl\._create_unverified_context", code):
            vulns.append({
                "vuln": "A05:2021-Security Misconfiguration",
                "severity": "MEDIUM",
                "detail": "Disabled SSL certificate verification detected."
            })
        return vulns

    def check_osv_vulnerability(self, package: str, version: str) -> dict:
        url = "https://api.osv.dev/v1/query"
        payload = {"version": version, "package": {"name": package, "ecosystem": "PyPI"}}
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            # Fallback for offline or test mode
            return {}

    def _check_compliance(self, text: str, role: str, violations: list, risk_score: float) -> tuple[float, str]:
        redacted_text = text
        if not self.config or not role:
            return risk_score, redacted_text

        profile_rel = self.config.roles.compliance_profiles.get(role)
        if not profile_rel:
            return risk_score, redacted_text

        paths_to_try = [
            Path("config") / profile_rel,
            Path(profile_rel),
            Path(__file__).resolve().parents[3] / "config" / profile_rel,
            Path(__file__).resolve().parents[3] / profile_rel,
        ]

        profile_path = None
        for p in paths_to_try:
            if p.exists():
                profile_path = p
                break

        if not profile_path:
            return risk_score, redacted_text

        try:
            profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            rules = profile.get("rules", [])
            for rule in rules:
                pat = re.compile(rule["pattern"], re.I)
                if pat.search(redacted_text):
                    violations.append({"check": "compliance", "detail": f"Violation of rule: {rule['name']}"})
                    risk_score += 0.5
                    if rule["action"] == "redact":
                        redacted_text = pat.sub("[REDACTED]", redacted_text)
        except Exception:
            pass

        return risk_score, redacted_text
