---
name: owasp-checker
description: Check code against OWASP Top 10 vulnerabilities and return a risk score with findings.
triggers:
  - owasp
  - security check
  - vulnerability
  - sql injection
  - xss
  - security scan
depends_on: []
output_schema:
  type: object
  properties:
    vulnerabilities:
      type: array
      items:
        type: object
    risk_score:
      type: integer
      minimum: 0
      maximum: 10
    passed:
      type: boolean
  required:
    - vulnerabilities
    - risk_score
    - passed
roles:
  - Dev
  - IT
model_tier: sonnet
---

# OWASP Top 10 Checker

Check code against OWASP Top 10. For each: A01 Broken Access Control, A02 Crypto Failures, A03 Injection (SQL/command/LDAP), A04 Insecure Design, A05 Security Misconfiguration, A06 Vulnerable Components, A07 Auth Failures, A08 Integrity Failures, A09 Logging Failures, A10 SSRF. Risk score 0-10. Passed = risk_score < 4 and no critical findings.

## OWASP Top 10 (2021) Checks

- **A01 Broken Access Control**: missing authorization checks, IDOR, path traversal
- **A02 Cryptographic Failures**: weak ciphers (MD5, SHA1), plain-text secrets, unencrypted sensitive data
- **A03 Injection**: SQL injection, command injection, LDAP injection, template injection
- **A04 Insecure Design**: missing rate limiting, insecure workflow logic
- **A05 Security Misconfiguration**: default credentials, verbose error messages, debug mode in prod
- **A06 Vulnerable and Outdated Components**: known CVEs in dependencies (cross-ref cve-lookup skill)
- **A07 Identification and Authentication Failures**: weak passwords, no MFA, session fixation
- **A08 Software and Data Integrity Failures**: unsigned packages, unsafe deserialization
- **A09 Security Logging and Monitoring Failures**: no audit logs, silent auth failures
- **A10 Server-Side Request Forgery (SSRF)**: unvalidated URLs in server-side HTTP calls

## Vulnerability Object Format

```json
{"id": "A03", "title": "Injection", "severity": "critical", "location": "line 88", "description": "Unsanitized user input in SQL query"}
```

## Risk Score Calculation

- critical finding: +3 per finding (max 10)
- high: +2
- medium: +1
- Passed = risk_score < 4 AND zero critical findings
