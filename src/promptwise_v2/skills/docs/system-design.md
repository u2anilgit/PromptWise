---
name: system-design
description: Create system design documentation with C4 diagrams and component specifications.
triggers:
  - system design
  - architecture diagram
  - c4 diagram
  - technical design
  - high level design
depends_on: []
output_schema:
  type: object
  properties:
    components:
      type: array
      items:
        type: object
    mermaid_c4:
      type: string
    adr_references:
      type: array
      items:
        type: string
  required:
    - components
    - mermaid_c4
roles:
  - Architect
model_tier: opus
---

# System Design Documentation

Create system design documentation. Generate: C4 Context → Container → Component diagrams in Mermaid syntax. For each component: {name, type, technology, responsibilities[], interfaces[]}. Include: data flow, scalability considerations, failure modes, ADR references. Output valid Mermaid C4 diagram.

## C4 Diagram Levels

### Level 1 — Context
Shows the system in its environment: users, external systems, and the system itself.

```mermaid
C4Context
  title System Context Diagram
  Person(user, "User", "Description")
  System(system, "System Name", "Description")
  System_Ext(external, "External System", "Description")
  Rel(user, system, "Uses")
  Rel(system, external, "Calls")
```

### Level 2 — Container
Shows the major deployable units (web app, API, database, message queue).

```mermaid
C4Container
  title Container Diagram
  Container(api, "API Server", "Python/FastAPI", "Handles requests")
  ContainerDb(db, "Database", "PostgreSQL", "Stores data")
  Rel(api, db, "Reads/Writes", "SQL")
```

### Level 3 — Component
Shows internal components of a single container.

## Component Specification

For each component output:
```json
{
  "name": "ComponentName",
  "type": "service | database | queue | cache | external",
  "technology": "Python/FastAPI",
  "responsibilities": ["responsibility 1", "responsibility 2"],
  "interfaces": ["REST /api/v1/...", "gRPC ServiceName"]
}
```

## Required Sections

1. **Data Flow** — sequence diagram showing primary request flow.
2. **Scalability** — how each component scales (horizontal/vertical), bottlenecks.
3. **Failure Modes** — what happens when each component fails, recovery strategy.
4. **ADR References** — list of architecture decisions that apply (e.g., `ADR-0001-use-postgresql.md`).

## Output

Return `components` array, `mermaid_c4` string (valid Mermaid C4 syntax), and `adr_references` array.
