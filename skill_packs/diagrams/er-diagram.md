---
name: er-diagram
description: "Generate entity-relationship diagrams as Mermaid erDiagram from a schema, model classes, or a described data model. Captures entities, attributes, keys, and cardinality."
triggers: ["er diagram", "entity relationship", "data model", "schema diagram", "database diagram", "erd"]
depends_on: []
output_schema:
  type: object
  properties:
    mermaid: {type: string}
  required: ["mermaid"]
roles: ["Dev", "Data", "Architect"]
model_tier: "sonnet"
---

# ER Diagram Skill

Produce a **Mermaid erDiagram** from a schema / ORM models / data description.

1. List entities (tables/models). For each, include key attributes with types and mark
   `PK` / `FK`.
2. Express relationships with cardinality:
   - `||--o{` one-to-many, `||--||` one-to-one, `}o--o{` many-to-many.
   - Label the relationship verb ("places", "contains").
3. Use exact field names/types when a real schema is provided; do not invent columns.
4. Output ONLY a fenced ```mermaid block + a one-line caption. Validate with the
   `validate_mermaid` tool first.

Example:
```mermaid
erDiagram
  SESSION ||--o{ COST_LOG : records
  TASK {
    string task_id PK
    string title
    string status
    float  estimate_hours
    float  tokens
  }
  COST_LOG {
    string log_id PK
    string session_id FK
    float  cost_usd
  }
```
