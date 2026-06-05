---
name: pii-detector
description: Detect personally identifiable information (PII) in text or code and return redacted output.
triggers:
  - pii
  - personal data
  - gdpr
  - email detection
  - phone number
  - ssn
  - privacy
depends_on: []
output_schema:
  type: object
  properties:
    pii_found:
      type: boolean
    items:
      type: array
      items:
        type: object
    action:
      type: string
      enum:
        - allow
        - warn
        - block
    redacted_output:
      type: string
  required:
    - pii_found
    - action
roles:
  - Dev
  - IT
model_tier: haiku
---

# PII Detector

Detect PII in text/code. Check for: email addresses (regex), SSNs (XXX-XX-XXXX), credit cards (16-digit patterns), phone numbers, names+addresses. For each find: {type, value_masked, location}. Default action: warn. Block if severity=critical. Return redacted version with PII replaced by [REDACTED-TYPE].

## PII Types to Detect

- **Email addresses**: match `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- **SSNs**: match `\d{3}-\d{2}-\d{4}` pattern
- **Credit cards**: match 16-digit sequences (with or without dashes/spaces)
- **Phone numbers**: match common US/international patterns (e.g., +1-800-555-0100)
- **Names + addresses**: heuristic detection of full names adjacent to street addresses

## Severity Rules

- Email alone: warn
- SSN or credit card: block (critical)
- Phone number: warn
- Name + full address: warn

## Output Format

For each PII item found, return:
```json
{"type": "email", "value_masked": "j***@example.com", "location": "line 42"}
```

Replace all PII in the output text with `[REDACTED-TYPE]` (e.g., `[REDACTED-EMAIL]`, `[REDACTED-SSN]`).
