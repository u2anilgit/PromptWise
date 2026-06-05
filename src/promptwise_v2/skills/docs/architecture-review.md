---
name: architecture-review
description: Review system architecture across 5 dimensions and produce a scored approval decision.
triggers:
  - architecture review
  - arch review
  - design review
  - technical review
  - system review
depends_on: []
output_schema:
  type: object
  properties:
    score:
      type: integer
      minimum: 0
      maximum: 100
    findings:
      type: array
      items:
        type: object
    approved:
      type: boolean
    recommendations:
      type: array
      items:
        type: string
  required:
    - score
    - findings
    - approved
roles:
  - Architect
  - EM
model_tier: opus
---

# Architecture Review

Review system architecture. Evaluate: (1) Scalability (can it 10x?), (2) Reliability (single points of failure?), (3) Security (threat surface, auth/authz), (4) Maintainability (coupling, cohesion, complexity), (5) Cost efficiency. Score each 0-20. Total 100. Findings per dimension: {severity, description, recommendation}. Approved if score >= 70 and no critical findings.

## Scoring Dimensions (0-20 each)

### 1. Scalability (0-20)
- Can the system handle 10x current load?
- Are there stateless services that can scale horizontally?
- Are databases shardable or readable via replicas?
- 20 = auto-scales seamlessly; 0 = single-node, no path to scale.

### 2. Reliability (0-20)
- Are there single points of failure (SPOF)?
- Is there circuit breaking, retry logic, and graceful degradation?
- What is the RTO/RPO?
- 20 = multi-region, no SPOF, tested failover; 0 = single instance, no backup.

### 3. Security (0-20)
- Is the threat surface minimized?
- Is authentication and authorization enforced at every boundary?
- Is data encrypted at rest and in transit?
- 20 = zero-trust, least privilege, pen-tested; 0 = no auth, plain text.

### 4. Maintainability (0-20)
- Is coupling low and cohesion high?
- Is cyclomatic complexity manageable?
- Is there clear ownership and documentation?
- 20 = clean architecture, tested, documented; 0 = monolithic spaghetti.

### 5. Cost Efficiency (0-20)
- Are resources right-sized?
- Are there obvious waste patterns (over-provisioned, idle resources)?
- Is caching used appropriately?
- 20 = optimized, autoscaled, cost-tagged; 0 = massively over-provisioned.

## Finding Format

Each finding:
```json
{
  "dimension": "Scalability",
  "severity": "critical | high | medium | low",
  "description": "Database has no read replicas — all reads hit primary",
  "recommendation": "Add read replica and route SELECT queries via replica"
}
```

## Approval Logic

- `approved = true` if `score >= 70` AND no findings with `severity == "critical"`.
- `approved = false` otherwise — list blocking findings explicitly.

## Output

Return `score` (integer 0-100), `findings` array, `approved` boolean, and `recommendations` array (top 3-5 actionable items).
