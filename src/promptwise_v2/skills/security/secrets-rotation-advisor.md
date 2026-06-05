---
name: secrets-rotation-advisor
description: Analyze codebase for hardcoded secrets and generate a prioritized rotation plan with remediation steps.
triggers:
  - rotate secrets
  - api key rotation
  - credential rotation
  - secret management
  - vault
depends_on: []
output_schema:
  type: object
  properties:
    secrets_found:
      type: array
      items:
        type: object
    rotation_plan:
      type: array
      items:
        type: string
    priority:
      type: string
      enum:
        - immediate
        - high
        - medium
        - low
  required:
    - secrets_found
    - rotation_plan
    - priority
roles:
  - Dev
  - IT
model_tier: sonnet
---

# Secrets Rotation Advisor

Analyze codebase for secrets needing rotation. Detect: hardcoded API keys, passwords in code, tokens in config files. For each: {type, location, exposure_risk, rotation_steps}. Generate rotation plan ordered by risk. Recommend secret management tool (AWS Secrets Manager, Vault, .env with gitignore).

## Secret Patterns to Detect

- API keys: `sk-`, `pk_live_`, `AKIA` (AWS), `ghp_` (GitHub), `xoxb-` (Slack)
- Passwords: assignments like `password = "..."`, `passwd = "..."`, `secret = "..."`
- Database URLs: `postgres://user:pass@host`, `mysql://user:pass@host`
- Generic tokens: 32+ character hex/base64 strings assigned to vars named `token`, `key`, `secret`
- Private keys: `-----BEGIN RSA PRIVATE KEY-----`, `-----BEGIN PRIVATE KEY-----`
- `.env` files committed to git

## Secret Object Format

```json
{"type": "aws_access_key", "location": "config/settings.py:14", "exposure_risk": "critical", "rotation_steps": ["Revoke key in AWS IAM console", "Generate new key pair", "Update in AWS Secrets Manager", "Remove from code"]}
```

## Priority Assignment

- `immediate`: private keys, production DB credentials, or any secret found in git history
- `high`: API keys for paid services (AWS, Stripe, Twilio)
- `medium`: internal service tokens, dev/staging credentials
- `low`: read-only API keys with no write access

## Recommended Tools

- **AWS**: AWS Secrets Manager or Parameter Store
- **General**: HashiCorp Vault, Doppler
- **Local dev**: `.env` file with `.gitignore` entry, `python-dotenv` / `dotenv` library

Return rotation_plan as ordered list of action strings, highest risk first.
