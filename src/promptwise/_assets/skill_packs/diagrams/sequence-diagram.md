---
name: sequence-diagram
description: "Generate sequence diagrams as Mermaid sequenceDiagram — show interactions, messages, and lifelines between actors/services over time, including async, loops, and alt branches."
triggers: ["sequence diagram", "interaction diagram", "message flow", "call sequence", "lifeline"]
depends_on: []
output_schema:
  type: object
  properties:
    mermaid: {type: string}
  required: ["mermaid"]
roles: ["Dev", "Architect"]
model_tier: "sonnet"
---

# Sequence Diagram Skill

Produce a **Mermaid sequenceDiagram** of an interaction.

1. Declare participants in call order: `participant U as User`.
2. Messages: `A->>B: request` (solid/sync), `B-->>A: response` (dashed/return).
3. Use `activate`/`deactivate` for lifelines, `loop`/`alt`/`opt`/`par` blocks for control.
4. Keep one message per line; label with the actual method/event.
5. Output ONLY a fenced ```mermaid block + a one-line caption. Validate with the
   `validate_mermaid` tool first.

Example:
```mermaid
sequenceDiagram
  participant U as User
  participant H as Hub
  participant M as MCP server
  U->>H: /promptwise route this
  H->>M: route_request(text)
  M-->>H: recommended_model
  H-->>U: "Use Sonnet — reason…"
```
