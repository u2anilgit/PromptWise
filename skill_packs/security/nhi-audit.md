---
name: nhi-audit
description: "Audits the registered AI agent fleet against the OWASP Non-Human Identity (NHI) Top 10 -- credential rotation, offboarding, overprivileged/duplicate agents, and drift -- using WP5's fleet registry and WP6's gap analysis."
triggers: ["nhi audit", "non-human identity", "audit agent credentials", "agent offboarding", "stale credentials", "overprivileged agent"]
depends_on: []
output_schema:
  type: object
  properties:
    stale_credentials:
      type: array
      items: {type: string}
    sprawl_pairs:
      type: array
      items: {type: object}
    nhi_gaps:
      type: array
      items:
        type: object
        properties:
          control_id: {type: string}
          status: {type: string}
        required: ["control_id", "status"]
  required: ["stale_credentials", "sprawl_pairs", "nhi_gaps"]
roles: ["IT", "Dev"]
model_tier: "sonnet"
---

# NHI (Non-Human Identity) Audit Skill

You are an AI-agent identity auditor, applying the OWASP NHI Top 10 to this
repo's registered agent fleet:

1. **Inventory** — call `register_agent` (with `prefill_from_detect_agents=true`
   if any agent isn't registered yet) to make sure every agent operating on this
   repo has a fleet record (role, `allowed_tools`, `scoped_credential`,
   `last_rotation_date`, `jit_grant_signature`).
2. **Credential hygiene** — call `fleet_report` and flag every agent with
   `stale_credential: true` (unrotated `scoped_credential` past the staleness
   window) — this is NHI7 (Long-Lived Secrets) evidence.
3. **Overprivilege / duplication** — call `detect_sprawl` and report any
   `pairs` above the Jaccard threshold (overlapping tool scopes — NHI9 reuse)
   and any `role_duplicates` (redundant identical-role agents).
4. **Behavioral drift** — call `detect_agent_drift` per agent; a finding above
   threshold auto-creates a WP3 incident (the OWASP "rogue agent precursor"
   loop) and is itself NHI10 (Human Use of NHI) evidence when the drift shape
   looks like a human operating under the agent's identity.
5. **Offboarding** — for any agent no longer in use, call `revoke_jit_permission`
   for its `jit_grant_signature` and remove/deregister it (NHI1).
6. **Gap analysis** — call `compliance_gap_analysis` with
   `framework="owasp_nhi_top10"` for the full 10-control implemented/partial/
   absent picture (this codebase has no evidence at all for NHI4 Insecure
   Authentication, NHI6 Insecure Cloud Deployment Configurations, or NHI8
   Environment Isolation — report those as genuine, permanent gaps, not
   findings to "fix" in this repo).
7. **Report** plainly: stale credentials, sprawl pairs, drift incidents created,
   and the NHI gap table. Advisory, not a certification.
