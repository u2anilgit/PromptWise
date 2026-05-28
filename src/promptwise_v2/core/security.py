import re
from promptwise_v2.types_v2 import SecurityResult

_CHECKS = ["syntax", "secrets", "destructive", "supply_chain", "permissions"]

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

_SYNTAX_INJECTION = [
    re.compile(r'ignore\s+(previous|prior|all)\s+instructions', re.I),
    re.compile(r'disregard\s+(your|all)\s+(instructions|rules)', re.I),
    re.compile(r'you\s+are\s+now\s+', re.I),
    re.compile(r'new\s+persona', re.I),
]

_PERMISSION_PATTERNS = [
    re.compile(r'\bsudo\b'),
    re.compile(r'\bchmod\s+[0-7]{3,4}\b'),
    re.compile(r'\bchown\s+root\b'),
    re.compile(r'\bsu\s+-\b'),
    re.compile(r'/etc/passwd'),
    re.compile(r'/etc/shadow'),
]


class SecurityChecker:
    def check(self, text: str) -> SecurityResult:
        violations = []
        risk_score = 0.0

        for pattern in _SYNTAX_INJECTION:
            if pattern.search(text):
                violations.append({"check": "syntax", "detail": pattern.pattern})
                risk_score += 0.4

        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                violations.append({"check": "secrets", "detail": pattern.pattern})
                risk_score += 0.8

        for pattern in _DESTRUCTIVE_PATTERNS:
            if pattern.search(text):
                violations.append({"check": "destructive", "detail": pattern.pattern})
                risk_score += 0.7

        for pattern in _SUPPLY_CHAIN_PATTERNS:
            if pattern.search(text):
                violations.append({"check": "supply_chain", "detail": pattern.pattern})
                risk_score += 0.9

        for pattern in _PERMISSION_PATTERNS:
            if pattern.search(text):
                violations.append({"check": "permissions", "detail": pattern.pattern})
                risk_score += 0.6

        risk_score = min(1.0, risk_score)
        passed = len(violations) == 0
        blocked = risk_score >= 0.7

        return SecurityResult(
            passed=passed,
            checks_run=_CHECKS[:],
            violations=violations,
            risk_score=round(risk_score, 3),
            blocked=blocked,
            details=f"{len(violations)} violation(s) found" if violations else "clean",
        )
