# PromptWise Architecture

Diagrams are Mermaid (plain text — render on GitHub). Generated with PromptWise's own
diagram skill packs and checked with `validate_mermaid`.

## Functional view

What PromptWise does and for whom — capabilities, not code.

```mermaid
flowchart TB
  dev([Developer]) --> hub["/promptwise hub skill"]
  hub --> mcp["MCP server (65+ tools)"]
  subgraph Capabilities
    opt[Optimization: route / compress / cache / batch]
    flow[Workflow planning]
    track[Task / effort / token tracking]
    diag[Diagram generation]
    sec[Security & compliance scanning]
    cost[Cost / budget / ROI]
  end
  mcp --> Capabilities
  Capabilities --> emit["Emitters: MCP · SKILL.md · AGENTS.md"]
  packs[("63 skill packs")] --> mcp
  store[("SQLite ~/.promptwise")] --> Capabilities
```

## Technical view

Modules and dependencies inside `src/promptwise/`.

```mermaid
flowchart LR
  server[server.py] --> core
  server --> security
  server --> plugins
  server --> db
  server --> config[config.py]
  subgraph core [core/]
    router[router]
    rewriter[rewriter]
    optimizer[optimizer]
    compression[compression]
    workflow[workflow_planner]
    tracker[task_tracker]
    mermaid[mermaid]
    skills[skill_loader]
  end
  subgraph security [security/]
    scanner[scanner]
    compliance[compliance]
  end
  subgraph db [db/]
    models[models]
  end
  tracker --> models
  skills --> packs[("skill_packs/")]
  config --> yaml[("config/*.yaml")]
```

## Data model (ER)

Local SQLite schema (`db/models.py`).

```mermaid
erDiagram
  SESSION ||--o{ COST_LOG : records
  SESSION ||--o{ MEMORY_ENTRY : logs
  SESSION {
    string session_id PK
    string started_ts
    string last_ping_ts
  }
  COST_LOG {
    string log_id PK
    string session_id FK
    string tool
    float  cost_usd
    float  input_tokens
  }
  TASK {
    string task_id PK
    string title
    string status
    float  estimate_hours
    float  actual_hours
    float  tokens
    float  cost_usd
  }
  ROI_STAT {
    string stat_id PK
    string developer
    float  tokens_saved
    float  hours_saved
  }
```

## Request flow (sequence)

A `route_request` call from the agent.

```mermaid
sequenceDiagram
  participant U as Developer
  participant H as /promptwise hub
  participant M as MCP server
  participant R as Router
  participant D as SQLite
  U->>H: "which model for this task?"
  H->>M: route_request(text, budget)
  M->>R: route(text, intent, stakes)
  R-->>M: recommended_model + reason
  M->>D: record_cost(tool, model, cost)
  M-->>H: model + reason + alternatives
  H-->>U: "Use Sonnet — reason…"
```
