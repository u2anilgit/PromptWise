---
name: flow-diagram
description: "Generate process / control-flow / data-flow diagrams as Mermaid flowcharts. Captures decisions, branches, loops, and swimlanes from a described process."
triggers: ["flow diagram", "flowchart", "process flow", "data flow", "control flow", "workflow diagram", "swimlane"]
depends_on: []
output_schema:
  type: object
  properties:
    mermaid: {type: string}
  required: ["mermaid"]
roles: ["Dev", "Analyst", "PM"]
model_tier: "sonnet"
---

# Flow Diagram Skill

Turn a described process into a **Mermaid flowchart**.

1. Identify start/end, steps, decisions (diamonds), and loops.
2. Use `flowchart TD` (top-down) for processes, `flowchart LR` for pipelines.
3. Decisions: `id{Question?} -->|yes| a` / `-->|no| b`.
4. For multi-actor processes use `subgraph Lane[Actor] ... end` as swimlanes.
5. Keep labels terse; one action per node.
6. Output ONLY a fenced ```mermaid block + a one-line caption. Validate with the
   `validate_mermaid` tool first.

Example:
```mermaid
flowchart TD
  A([Start]) --> B[Receive request]
  B --> C{Cached?}
  C -->|yes| D[Return cached]
  C -->|no| E[Route to model]
  E --> F[Record cost] --> G([End])
  D --> G
```
