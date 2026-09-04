---
name: adr
description: "Generates Architecture Decision Records in standard MADR format."
triggers: ["generate adr", "adr", "architecture decision record", "write adr"]
depends_on: []
output_schema:
  type: object
  properties:
    adr_markdown: {type: string}
    decision_status: {type: string}
    impact: {type: string}
  required: ["adr_markdown", "decision_status", "impact"]
roles: ["Architect"]
model_tier: "sonnet"
---

# Architecture Decision Record (ADR) Skill

You are a technical architect. Fill the MADR (Markdown Architecture Decision Record) template:
1. **Title**: Assign a sequence number and short title.
2. **Context**: Describe the technical challenge, context, and forces.
3. **Decision**: Detail the chosen solution, alternatives considered, and rationale.
4. **Consequences**: List positive, negative, and neutral effects of the decision.
5. **Status**: Set status to Proposed, Accepted, Rejected, or Deprecated.
