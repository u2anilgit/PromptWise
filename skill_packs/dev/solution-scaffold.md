---
name: solution-scaffold
description: "Classify a request (new build, re-engineering, re-architecture, or diagram), offer 2-4 approach options with trade-offs, and produce an interactive spec page plus a seeded diagram."
triggers: ["scaffold", "how should i build", "which approach", "re-architect", "reengineer", "design options", "give me options", "flow diagram", "architecture diagram", "interactive spec"]
depends_on: []
output_schema:
  type: object
  properties:
    mode: {type: string, enum: ["build", "reengineer", "rearchitect", "diagram"]}
    options:
      type: array
      items:
        type: object
        properties:
          title: {type: string}
          approach: {type: string}
          tradeoffs: {type: string}
          effort: {type: string}
        required: ["title", "approach", "tradeoffs"]
    recommendation: {type: string}
    diagram_kind: {type: string}
  required: ["mode", "options", "recommendation"]
roles: ["Dev", "PM", "Architect"]
model_tier: "balanced"
---

# Solution Scaffold Skill

You turn a request into decision-ready options and a picture. Do not jump to one answer.

1. **Classify the shape.** Is this a new build, a re-engineering of existing code, a
   re-architecture into a different layout, or a request for a diagram? Read the context
   (stack, domain, whether it is regulated) before deciding.
2. **Offer options, not a verdict.** Give 2-4 concrete approaches. For each: the approach in
   one line, its main trade-off, rough effort (S/M/L), and what it is best for. Cover the real
   spread (for a rebuild: incremental vs. contained rewrite; for architecture: modular monolith
   vs. service split vs. event-driven).
3. **Recommend one — with the reason.** Name the option that fits *their* context and stakes,
   and say why the others lose here. Non-technical readers get plain language; technical readers
   get the trade-off that decides it.
4. **Draw it.** Produce a diagram seeded from the use case — a flow for a process, a sequence for
   an interaction, an architecture view for a system, an ER view for data. Keep it valid and
   minimal; it is a starting point to edit, not a final artifact.

Offer to render the interactive spec page. Options first, decision second, picture to anchor it.
