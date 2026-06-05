---
name: code-review
description: Structured code review checking correctness, security, performance, and maintainability with a 0-100 score.
triggers:
  - review
  - code review
  - review this
  - check this code
  - pr review
depends_on: []
output_schema:
  type: object
  properties:
    issues:
      type: array
      items:
        type: object
      description: List of issues found, each with severity, description, file, line, and fix
    score:
      type: integer
      minimum: 0
      maximum: 100
      description: Overall code quality score from 0 to 100
    approved:
      type: boolean
      description: Whether the code is approved (score >= 80 and no critical issues)
    suggestions:
      type: array
      items:
        type: string
      description: Optional improvement suggestions that do not block approval
  required:
    - issues
    - score
    - approved
    - suggestions
roles:
  - Dev
  - EM
model_tier: sonnet
---

# Code Review

Structured code review. Check: correctness, security, performance, maintainability. Score 0-100 (>=80 = approve). For each issue: {severity: critical/high/medium/low, description, file, line, fix}. Never approve if critical issues exist.

## Review Dimensions

### Correctness
- Does the code do what it claims to do?
- Are all edge cases handled (null/empty/boundary values)?
- Are error conditions caught and handled appropriately?
- Are there off-by-one errors, incorrect comparisons, or logic bugs?

### Security
- Are inputs validated and sanitized?
- Are there SQL injection, XSS, or command injection risks?
- Are secrets or credentials hardcoded?
- Are file paths and user-supplied data handled safely?

### Performance
- Are there N+1 query patterns or nested loops on large collections?
- Are expensive operations called unnecessarily (in hot loops, on every request)?
- Is memory allocated and released correctly?

### Maintainability
- Is the code readable? Are names clear and accurate?
- Are functions and classes focused on a single responsibility?
- Is there duplication that should be extracted?
- Are comments present where the code is non-obvious?

## Severity Definitions

- **critical**: Must fix before merge. Introduces bugs, security vulnerabilities, or data loss.
- **high**: Should fix before merge. Significant correctness or performance issues.
- **medium**: Fix in follow-up. Code quality, minor correctness risks.
- **low**: Optional improvement. Style, naming, minor readability.

## Scoring

- Start at 100. Deduct: critical=25, high=10, medium=3, low=1.
- Score ≥80 AND no critical issues → `approved: true`.
- Any critical issue → `approved: false` regardless of score.

## Issue Format

Each issue in the `issues` array must include:
```
{
  "severity": "critical|high|medium|low",
  "description": "clear description of the problem",
  "file": "path/to/file.py",
  "line": 42,
  "fix": "concrete fix recommendation"
}
```

## Output

Return the full issues list, numeric score, approval status, and any non-blocking suggestions.
