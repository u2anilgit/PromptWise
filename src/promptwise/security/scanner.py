import re
import urllib.request
import json

from promptwise.types import SecurityResult
from promptwise.config import SecurityConfig

_SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|secret|password|token|sk-)[=:\s]["\']?[a-z0-9\-_]{8,}'),
    re.compile(r'(?i)bearer\s+[a-z0-9\-_\.]{20,}'),
    # Spaced assignment with optional quotes: API_KEY = "sk-...", password: 'hunter2pass'.
    # Requires an explicit ':' or '=' separator so plain identifiers (passwordHasher) don't match.
    re.compile(r'(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*["\']?[a-z0-9\-_]{8,}'),
]
_DESTRUCTIVE_PATTERNS = [
    re.compile(r'\brm\s+-rf\b'), re.compile(r'\bdrop\s+table\b', re.I),
    re.compile(r'\bdelete\s+from\b', re.I), re.compile(r'\bformat\s+[a-z]:\b', re.I),
    re.compile(r'\btruncate\b', re.I),
]
_SUPPLY_CHAIN_PATTERNS = [
    re.compile(r'pip\s+install\s+.*http://', re.I), re.compile(r'npm\s+install\s+.*http://', re.I),
    re.compile(r'curl\s+.*\|\s*(bash|sh)\b', re.I), re.compile(r'wget\s+.*\|\s*(bash|sh)\b', re.I),
]
_PERMISSION_PATTERNS = [
    re.compile(r'\bsudo\b'), re.compile(r'\bchmod\s+[0-7]{3,4}\b'),
    re.compile(r'\bchown\s+root\b'), re.compile(r'/etc/passwd'), re.compile(r'/etc/shadow'),
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
    re.compile(r'you\s+are\s+now\s+', re.I), re.compile(r'dan\s+mode|jailbreak', re.I),
]


class SecurityScanner:
    def __init__(self, config: SecurityConfig | None = None):
        self.config = config or SecurityConfig()

    def check(self, text: str) -> SecurityResult:
        violations = []
        risk_score = 0.0
        redacted = text

        for pattern in _INJECTION_PATTERNS:
            if pattern.search(redacted):
                violations.append({"check": "syntax", "detail": pattern.pattern})
                risk_score += 0.4

        for pattern in _SECRET_PATTERNS:
            if pattern.search(redacted):
                violations.append({"check": "secrets", "detail": pattern.pattern})
                risk_score += 0.8

        for pattern in _DESTRUCTIVE_PATTERNS:
            if pattern.search(redacted):
                violations.append({"check": "destructive", "detail": pattern.pattern})
                risk_score += 0.7

        for pattern in _SUPPLY_CHAIN_PATTERNS:
            if pattern.search(redacted):
                violations.append({"check": "supply_chain", "detail": pattern.pattern})
                risk_score += 0.9

        pip_matches = re.findall(r'pip\s+install\s+([a-zA-Z0-9-_]+)==([0-9.]+)', redacted)
        for pkg, ver in pip_matches:
            osv = self._check_osv(pkg, ver)
            if osv and "vulns" in osv:
                violations.append({"check": "supply_chain", "detail": f"OSV vulnerability: {pkg}=={ver}"})
                risk_score += 0.8

        for pattern in _PERMISSION_PATTERNS:
            if pattern.search(redacted):
                violations.append({"check": "permissions", "detail": pattern.pattern})
                risk_score += 0.6

        if self.config.pii_detection:
            for label, pattern in _PII_PATTERNS:
                if pattern.search(redacted):
                    violations.append({"check": "pii", "detail": f"Found PII: {label}"})
                    risk_score += 0.5
                    if self.config.pii_action == "redact":
                        redacted = pattern.sub(f"[REDACTED_{label.upper()}]", redacted)

        if self.config.injection_detection:
            for pattern in _INJECTION_PATTERNS:
                if pattern.search(redacted):
                    violations.append({"check": "injection", "detail": f"Injection: {pattern.pattern}"})
                    risk_score += 0.6

        risk_score = min(1.0, risk_score)
        return SecurityResult(
            passed=len(violations) == 0,
            checks_run=self.config.checks,
            violations=violations,
            risk_score=round(risk_score, 3),
            blocked=risk_score >= 0.7,
            details=f"{len(violations)} violation(s)" if violations else "clean",
        )

    def check_owasp(self, code: str) -> list[dict]:
        vulns = []
        if re.search(r"(execute|query)\s*\(\s*(f['\"].*?\{|['\"].*?\s*\+\s*\w+)", code, re.I):
            vulns.append({"vuln": "A03:2021-SQL Injection", "severity": "HIGH",
                          "detail": "Raw string in SQL execution. Use parameterized queries."})
        if re.search(r"\b(os\.system|subprocess\.(Popen|run)|eval|exec)\b", code):
            vulns.append({"vuln": "A03:2021-Command Injection", "severity": "HIGH",
                          "detail": "OS command execution or eval on untrusted input."})
        if re.search(r"ssl\._create_unverified_context", code):
            vulns.append({"vuln": "A05:2021-Security Misconfiguration", "severity": "MEDIUM",
                          "detail": "SSL certificate verification disabled."})
        return vulns

    def _check_osv(self, package: str, version: str) -> dict:
        try:
            req = urllib.request.Request(
                "https://api.osv.dev/v1/query",
                data=json.dumps({"version": version, "package": {"name": package, "ecosystem": "PyPI"}}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return {}
