---
name: verification-before-completion
description: Pre-completion checklist verifying tests pass, no TODOs, docs updated, no secrets, and security checks clean.
triggers:
  - verify
  - verification
  - done check
  - pre-commit check
  - checklist
  - ready to ship
depends_on: []
output_schema:
  type: object
  properties:
    tests_pass:
      type: boolean
      description: Whether all tests in the test suite pass
    no_todos:
      type: boolean
      description: Whether there are no TODO or FIXME comments in changed code
    docs_updated:
      type: boolean
      description: Whether documentation and comments have been updated to reflect changes
    security_clear:
      type: boolean
      description: Whether no hardcoded secrets or security issues were found
    all_clear:
      type: boolean
      description: Whether all checks passed and the work is ready to complete
  required:
    - tests_pass
    - no_todos
    - docs_updated
    - security_clear
    - all_clear
roles:
  - Dev
model_tier: haiku
---

# Verification Before Completion

Pre-completion checklist. Only set all_clear=true if all checks pass.

## Checklist

Run each check and record true/false:

### 1. Tests Pass (`tests_pass`)
Run the full test suite. Every test must pass. No skipped tests unless they were already skipped before this change. If tests fail, return `all_clear: false` immediately.

### 2. No TODOs (`no_todos`)
Search changed files for `TODO`, `FIXME`, `HACK`, `XXX`, `TEMP`. Any occurrence in new or modified code sets this to false. TODOs in unchanged code do not count.

### 3. Docs Updated (`docs_updated`)
Check that:
- Docstrings/comments describe new or modified functions accurately.
- Any public API changes are reflected in documentation.
- README or CHANGELOG updated if user-facing behavior changed.

### 4. Security Clear (`security_clear`)
Scan changed code for:
- Hardcoded passwords, tokens, API keys, or credentials.
- Disabled security controls (e.g., `verify=False`, `SECURE=False`, `DEBUG=True` in production config).
- User input passed directly to shell commands, SQL queries, or file paths without sanitization.

### 5. All Clear (`all_clear`)
Set to `true` only if ALL four above checks are `true`. If any single check fails, `all_clear` must be `false`.

## Rules

- Never set `all_clear: true` if any check is false.
- Do not rationalize failures ("it's just a TODO, it's fine") — the check is binary.
- If a check cannot be determined, default to `false`.
