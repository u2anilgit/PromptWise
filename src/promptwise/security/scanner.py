import re
import secrets as _secrets
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
# Weighted, family-grouped injection patterns. Each entry is
# ``(compiled, weight, family)``; ``detect_injection`` sums the weights of the
# matched families (capped at 1.0) for a confidence score, replacing the old
# ``matches * 0.25`` count heuristic. Patterns require a trigger word to sit
# next to an adversarial object (e.g. an override verb next to an
# instructions/rules/prompt noun) so benign near-misses (a "ready to deploy"
# persona phrase, "override the default timeout") do not false-positive.
# Benchmarked offline in ``security/injection_benchmark.py`` (Phase 13.1).
_INJECTION_PATTERNS = [
    # instruction override: an override verb sitting next to an instruction noun
    (re.compile(r'(?i)\b(ignore|disregard|forget|override|bypass|skip)\b'
                r'[^.\n]{0,32}\b(instruction|instructions|rule|rules|prompt|prompts|'
                r'directive|directives|guardrail|guardrails|guideline|guidelines|'
                r'system\s+message)\b'), 0.8, "instruction_override"),
    # unfiltered / unrestricted persona request
    (re.compile(r'(?i)\b(unfiltered|unrestricted|jailbroken|no\s+restrictions|'
                r'no\s+filter|without\s+(any\s+)?(restrictions|filters|guardrails|'
                r'rules|limits))\b'), 0.7, "unfiltered_persona"),
    # jail-break keywords
    (re.compile(r'(?i)\b(jail\s?break|do\s+anything\s+now|dan\s+mode)\b'), 0.8, "jail_break"),
    # developer / god "mode"
    (re.compile(r'(?i)\b(developer|god)\s+mode\b'), 0.5, "developer_mode"),
    # persona reassignment to an adversarial role
    (re.compile(r'(?i)\b(you\s+are\s+now|from\s+now\s+on[, ]+you\s+are|'
                r'you\s+will\s+now\s+be)\b[^.\n]{0,20}\b(dan|an?|going\s+to|unfiltered|'
                r'unrestricted|evil|malicious|hacker|jailbroken)\b'), 0.6, "persona_reassign"),
    # system-prompt exfiltration: a reveal verb before a prompt/instructions object
    (re.compile(r'(?i)\b(reveal|repeat|print|show|expose|leak|display|reprint|'
                r'output|tell\s+me)\b[^.\n]{0,28}\b(system\s+prompt|'
                r'your\s+(initial\s+|system\s+)?(instructions|prompt|rules)|'
                r'the\s+prompt\s+above)\b'), 0.7, "prompt_exfiltration"),
    # embedded role marker (indirect injection via a fake system/assistant turn)
    (re.compile(r'(?im)(^|\n)\s*(system|assistant|developer)\s*:'), 0.5, "embedded_role_marker"),
    (re.compile(r'(?i)\b(new\s+instructions?|begin\s+new\s+task|new\s+task)\s*:'),
     0.6, "embedded_task_marker"),
]


class SecurityScanner:
    def __init__(self, config: SecurityConfig | None = None):
        self.config = config or SecurityConfig()

    def detect_injection(self, text: str) -> tuple[bool, float, list[str]]:
        """Match text against known prompt-injection / instruction-override patterns.

        Returns ``(detected, confidence in [0,1], matched pattern strings)``.
        Shared by ``check()`` and the standalone ``prompt_injection`` tool so
        there is exactly one place that knows what an injection looks like.
        """
        found: list[str] = []
        confidence = 0.0
        for pattern, weight, family in _INJECTION_PATTERNS:
            if pattern.search(text):
                found.append(family)
                confidence += weight
        return bool(found), round(min(1.0, confidence), 3), found

    # ── indirect prompt-injection canary (Rebuff-style) ──────────────────
    def issue_canary(self, prefix: str = "pw-canary") -> str:
        """Mint a fresh, hard-to-guess canary token.

        Embed it into content that will flow through tool output / RAG with
        ``embed_canary``; if it later surfaces in model output
        (``check_canary_leak``) the injected content leaked back out — the
        exfiltration signature of an indirect prompt injection.
        """
        return f"{prefix}-{_secrets.token_hex(12)}"

    def embed_canary(self, content: str, token: str) -> str:
        """Hide ``token`` in ``content`` as a trailing HTML comment, so it
        rides along with tool-output/RAG text without altering the visible
        body. Returns ``content`` unchanged if no token is supplied."""
        if not token:
            return content
        return f"{content}\n<!-- canary:{token} -->"

    def check_canary_leak(self, output: str, token: str) -> bool:
        """True iff a previously-issued canary ``token`` appears in model
        ``output`` — i.e. tool-output/RAG content leaked back into the
        response. Empty token means nothing to check."""
        return bool(token) and token in (output or "")

    def detect_pii(self, text: str, *, redact: bool = False) -> tuple[list[dict], str]:
        """Scan text for PII patterns.

        Returns ``(items, possibly-redacted text)`` where each item is
        ``{"type": label, "count": n}``. Shared by ``check()`` and the
        standalone ``scan_response`` tool.
        """
        items: list[dict] = []
        redacted = text
        for label, pattern in _PII_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                items.append({"type": label, "count": len(matches)})
                if redact:
                    redacted = pattern.sub(f"[REDACTED_{label.upper()}]", redacted)
        return items, redacted

    def check(self, text: str, *, allow_network: bool = False) -> SecurityResult:
        violations = []
        risk_score = 0.0
        redacted = text

        detected, _, inj_patterns = self.detect_injection(redacted)
        if detected:
            for p in inj_patterns:
                violations.append({"check": "syntax", "detail": p})
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
            osv = self._check_osv(pkg, ver, allow_network=allow_network)
            if osv and "vulns" in osv:
                violations.append({"check": "supply_chain", "detail": f"OSV vulnerability: {pkg}=={ver}"})
                risk_score += 0.8

        for pattern in _PERMISSION_PATTERNS:
            if pattern.search(redacted):
                violations.append({"check": "permissions", "detail": pattern.pattern})
                risk_score += 0.6

        if self.config.pii_detection:
            pii_items, redacted = self.detect_pii(redacted, redact=(self.config.pii_action == "redact"))
            for item in pii_items:
                violations.append({"check": "pii", "detail": f"Found PII: {item['type']}"})
                risk_score += 0.5

        if self.config.injection_detection:
            for p in inj_patterns:
                violations.append({"check": "injection", "detail": f"Injection: {p}"})
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
        if (re.search(r"(execute|query)\s*\(\s*(f['\"].*?\{|['\"].*?\s*\+\s*\w+)", code, re.I)
                or re.search(r'f["\'].*?(SELECT|INSERT|UPDATE|DELETE).*?\{', code, re.I)):
            vulns.append({"category": "A03:2021-SQL Injection", "severity": "critical",
                          "description": "Raw/f-string interpolation in SQL execution. Use parameterized queries."})
        if re.search(r'(?i)(password|api[_-]?key|secret)\s*=\s*["\'][^"\']{4,}["\']', code):
            vulns.append({"category": "A07:2021-Hardcoded Secrets", "severity": "critical",
                          "description": "Hardcoded credential."})
        if re.search(r'(innerHTML|document\.write)\s*[=\(]', code):
            vulns.append({"category": "A03:2021-XSS", "severity": "high",
                          "description": "Unsafe DOM write."})
        if re.search(r"\b(os\.system|subprocess\.(Popen|run|call)|eval|exec)\b", code):
            vulns.append({"category": "A03:2021-Command Injection", "severity": "high",
                          "description": "OS command execution or eval on untrusted input."})
        if re.search(r"ssl\._create_unverified_context", code):
            vulns.append({"category": "A05:2021-Security Misconfiguration", "severity": "medium",
                          "description": "SSL certificate verification disabled."})
        # A02: weak hashing / broken ciphers.
        if re.search(r"(?i)\bhashlib\.(md5|sha1)\b|\b(md5|sha1)\s*\(", code) or \
                re.search(r"\b(DES|RC4)\b", code):
            vulns.append({"category": "A02:2021-Cryptographic Failures", "severity": "high",
                          "description": "Weak hash (MD5/SHA1) or broken cipher (DES/RC4). "
                                         "Use SHA-256+/AES."})
        # A08: insecure deserialization. yaml.load is unsafe unless a safe loader is used.
        if re.search(r"\b(pickle\.loads|marshal\.loads)\s*\(", code) or (
                re.search(r"\byaml\.load\s*\(", code)
                and not re.search(r"safe_load|SafeLoader|Loader\s*=", code)):
            vulns.append({"category": "A08:2021-Software and Data Integrity Failures",
                          "severity": "high",
                          "description": "Insecure deserialization (pickle/marshal/unsafe yaml.load) "
                                         "on untrusted data. Use a safe loader."})
        # A10: SSRF — request on a non-literal (variable) URL.
        if re.search(r"(?i)\b(requests\.(get|post|put|delete|head|patch)|urlopen)"
                     r"\s*\(\s*(?!['\"])[A-Za-z_]", code):
            vulns.append({"category": "A10:2021-Server-Side Request Forgery (SSRF)",
                          "severity": "high",
                          "description": "Request issued to a non-literal URL. Validate/allow-list "
                                         "the destination host."})
        # A01: path traversal into a file open.
        if re.search(r"\bopen\s*\([^)\n]*\.\.[\\/]", code):
            vulns.append({"category": "A01:2021-Broken Access Control (Path Traversal)",
                          "severity": "high",
                          "description": "Path traversal in a file open. Normalize and confine to a "
                                         "base directory."})
        # A05: debug mode left enabled.
        if re.search(r"(?i)\bdebug\s*=\s*True\b", code):
            vulns.append({"category": "A05:2021-Security Misconfiguration", "severity": "medium",
                          "description": "Debug mode enabled. Disable in production."})
        return vulns

    def _check_osv(self, package: str, version: str, *, allow_network: bool = False) -> dict:
        if not allow_network:
            return {}
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
