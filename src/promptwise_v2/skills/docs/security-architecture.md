---
name: security-architecture
description: STRIDE threat modeling for system components with risk matrix and mitigation plan.
triggers:
  - security architecture
  - threat model
  - stride
  - security design
  - attack surface
depends_on: []
output_schema:
  type: object
  properties:
    threats:
      type: array
      items:
        type: object
      description: Threats identified per STRIDE category
    risk_matrix:
      type: object
      description: Likelihood x impact matrix
    mitigations:
      type: array
      items:
        type: object
      description: Mitigation plan per threat
  required:
    - threats
    - mitigations
roles:
  - Architect
  - IT
model_tier: opus
---

# Security Architecture — STRIDE Threat Modeling

STRIDE threat modeling. For each component: identify Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege threats. Risk matrix: likelihood × impact = risk score. For each threat: {type, description, risk_score, mitigation, residual_risk}. Output: threat list + risk matrix + mitigation plan.

## STRIDE Categories

| Letter | Threat | Violates |
|--------|--------|----------|
| S | Spoofing | Authentication |
| T | Tampering | Integrity |
| R | Repudiation | Non-repudiation |
| I | Information Disclosure | Confidentiality |
| D | Denial of Service | Availability |
| E | Elevation of Privilege | Authorization |

## Threat Format

For each identified threat:
```json
{
  "id": "T-001",
  "component": "API Gateway",
  "type": "Spoofing",
  "description": "Attacker replays stolen JWT token to impersonate user",
  "likelihood": 3,
  "impact": 4,
  "risk_score": 12,
  "mitigation": "Implement token binding and short expiry (15 min); use refresh token rotation",
  "residual_risk": 3
}
```

## Risk Scoring

- **Likelihood**: 1 (rare) → 5 (almost certain)
- **Impact**: 1 (negligible) → 5 (catastrophic)
- **Risk Score** = likelihood × impact (1-25)
- Risk levels: 1-5 Low, 6-12 Medium, 13-19 High, 20-25 Critical

## Risk Matrix

Output a 5×5 matrix (likelihood rows × impact columns) with threat IDs placed in cells.

## Mitigation Plan

Prioritize by risk score descending. For each mitigation:
```json
{
  "threat_id": "T-001",
  "control_type": "preventive | detective | corrective",
  "control": "Description of security control",
  "owner": "team or role responsible",
  "timeline": "immediate | sprint | quarter"
}
```

## Output

Return `threats` array, `risk_matrix` object (5×5 grid), and `mitigations` array sorted by risk score descending.
