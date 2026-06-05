---
name: runbook-generator
description: Generate operational runbooks and incident response playbooks for services.
triggers:
  - runbook
  - incident response
  - playbook
  - ops runbook
  - on-call
  - escalation procedure
  - sre
depends_on: []
output_schema:
  type: object
  properties:
    service_name:
      type: string
    runbook_type:
      type: string
      enum: [operations, incident-response, deployment, rollback]
    steps:
      type: array
      items:
        type: object
    escalation_path:
      type: array
      items:
        type: string
  required:
    - service_name
    - runbook_type
    - steps
roles:
  - Dev
  - IT
model_tier: sonnet
---

# Runbook Generator

Generate operational runbook or incident response playbook. Sections: (1) Service overview (purpose, dependencies, SLA). (2) Health checks (how to verify service is healthy). (3) Common issues + remediation steps (symptom → diagnosis → fix). (4) Escalation path (L1→L2→L3 with contacts). (5) Rollback procedure. For incident response: severity levels (P1/P2/P3), response times, communication templates. Each step: {action, command, expected_output, if_fails}.

## Section 1 — Service Overview

- **Purpose**: what the service does and who depends on it
- **Dependencies**: upstream services, databases, queues, external APIs
- **SLA**: availability target (e.g., 99.9%), RTO (Recovery Time Objective), RPO (Recovery Point Objective)
- **Owners**: primary on-call team, secondary escalation contacts
- **Dashboards**: links to monitoring dashboards, logs, traces

## Section 2 — Health Checks

For each health check define:
```
{
  action: "check description",
  command: "curl -sf https://service/health | jq .status",
  expected_output: "\"healthy\"",
  if_fails: "proceed to Section 3, issue X"
}
```

Standard health checks:
- HTTP health endpoint: `GET /health` → `{ status: "healthy", version: "...", uptime: ... }`
- Database connectivity: query a lightweight table or ping
- Dependency health: check upstream service health endpoints
- Queue depth: alert if queue depth exceeds threshold
- Error rate: check error rate in APM (target <0.1% for P1 services)

## Section 3 — Common Issues and Remediation

For each known issue:
```
Symptom: [what the alert or user report says]
Diagnosis:
  1. {action, command, expected_output, if_fails}
  2. ...
Fix:
  1. {action, command, expected_output, if_fails}
Verification:
  1. {action, command, expected_output}
```

Always include:
- High memory / OOM → restart pod, check for memory leak, review recent deploys
- Database connection exhaustion → check connection pool config, kill idle connections
- Upstream dependency failure → circuit breaker status, fallback behavior
- High latency → check slow query log, cache hit rate, downstream service latency
- Disk space → identify large files, rotate logs, extend volume

## Section 4 — Escalation Path

```
L1 (On-call engineer, 0-15 min):
  - Contact: PagerDuty rotation / Slack #on-call
  - Actions: triage, apply runbook fixes, escalate if unresolved in 15 min

L2 (Service owner, 15-30 min):
  - Contact: [service owner name / email / Slack handle]
  - Actions: deeper diagnosis, code-level investigation, hotfix deployment

L3 (Engineering Manager / VP Engineering, 30+ min or P1):
  - Contact: [EM name / phone]
  - Actions: executive communication, war room coordination, external vendor escalation
```

## Section 5 — Rollback Procedure

```
Trigger: deploy caused incident or error rate spike
Steps:
  1. Identify last known good version: git log --oneline -10
  2. Trigger rollback: kubectl rollout undo deployment/<name>
     or: deploy pipeline → Rollback → select previous version
  3. Verify rollback: check health endpoint + error rate
  4. Post-rollback: create incident ticket, notify stakeholders
```

## Incident Response Severity Levels

| Severity | Criteria | Response Time | Communication |
|----------|----------|--------------|---------------|
| P1 | Production down, all users impacted | 15 min | Status page + exec alert |
| P2 | Partial outage or major feature broken | 30 min | Status page update |
| P3 | Minor issue, workaround available | 2 hours | Internal ticket |

### Communication Template (P1)
```
INCIDENT: [service] is [symptom] since [time]
IMPACT: [# affected users / % of traffic]
STATUS: Investigating / Identified / Monitoring / Resolved
NEXT UPDATE: [time]
INCIDENT COMMANDER: [name]
```

## Output

Return structured runbook with all 5 sections, service metadata, step-by-step procedures with commands and expected outputs, escalation path with contacts, and rollback procedure.
