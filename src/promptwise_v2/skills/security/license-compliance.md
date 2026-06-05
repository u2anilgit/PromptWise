---
name: license-compliance
description: Check dependency licenses for open source compliance and flag policy violations.
triggers:
  - license
  - compliance
  - open source license
  - gpl
  - mit
  - apache
  - copyright
depends_on: []
output_schema:
  type: object
  properties:
    licenses_found:
      type: array
      items:
        type: object
    violations:
      type: array
      items:
        type: string
    compliant:
      type: boolean
    policy:
      type: string
  required:
    - licenses_found
    - compliant
roles:
  - Dev
  - IT
model_tier: haiku
---

# License Compliance Checker

Check dependency licenses for compliance. Permissive (allow): MIT, Apache-2.0, BSD-2/3, ISC. Copyleft (warn): LGPL. Copyleft-block (fail): GPL, AGPL. For each dep: detect license from package metadata. Flag incompatible combinations. Report policy applied (permissive/copyleft-warn/copyleft-block).

## License Categories

- **Permissive (allow)**: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, Unlicense, CC0
- **Copyleft-weak (warn)**: LGPL-2.0, LGPL-2.1, LGPL-3.0, MPL-2.0
- **Copyleft-strong (block)**: GPL-2.0, GPL-3.0, AGPL-3.0

## Detection Method

Read license from:
1. `package.json` → `license` field
2. `pyproject.toml` / `setup.py` → `license` classifiers
3. `go.mod` → lookup via pkg.go.dev
4. `Cargo.toml` → `license` field

## License Object Format

```json
{"package": "requests", "version": "2.31.0", "license": "Apache-2.0", "category": "permissive", "action": "allow"}
```

## Compliance Rules

- Any GPL/AGPL dependency in a proprietary project: add to `violations`, set `compliant: false`
- LGPL in a statically-linked project: warn
- Unknown license: warn and include in violations as "unknown-license: <package>"

Report the strictest policy applied across all dependencies.
