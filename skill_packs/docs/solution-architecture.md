---
name: solution-architecture
description: "Produce a solution architecture: context + container (C4), key decisions, NFRs/quality attributes, and tradeoffs. Pairs with the architecture-diagram and system-design packs to emit diagrams alongside the writeup."
triggers: ["solution architecture", "solution design", "c4 model", "architecture proposal", "nfr", "quality attributes", "tradeoff analysis"]
depends_on: ["architecture-diagram", "system-design"]
output_schema:
  type: object
  properties:
    context: {type: string}
    decisions: {type: array, items: {type: string}}
    nfrs: {type: array, items: {type: string}}
    diagram: {type: string}
  required: ["context", "decisions"]
roles: ["Architect", "Dev"]
model_tier: "opus"
---

# Solution Architecture Skill

Deliver a focused solution architecture for the described system.

1. **Context** — problem, users, constraints, scope boundaries (what's out).
2. **C4 levels** (only as deep as needed):
   - Level 1 Context — system + external actors/systems.
   - Level 2 Container — apps, services, data stores, and protocols between them.
   - (Component/Code only on request.)
   Call the `architecture-diagram` pack to render each level as Mermaid; embed the
   diagrams in the writeup.
3. **Key decisions** — list as lightweight ADRs (decision, why, alternatives rejected).
   Use the `adr` pack for any decision that needs a full record.
4. **NFRs / quality attributes** — performance, scalability, availability, security,
   cost, operability — each with a concrete target and how the design meets it.
5. **Risks & tradeoffs** — name what this design sacrifices and the mitigation.

Keep it pragmatic and sized to the problem; do not produce a 40-page document for a
small service.
