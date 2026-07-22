# PromptWise Architecture

Diagrams are Mermaid (plain text — render on GitHub). Generated with PromptWise's own
diagram skill packs and checked with `validate_mermaid`.

## Functional view

What PromptWise does and for whom — capabilities, not code.

```mermaid
flowchart TB
  dev([Developer]) --> hub["/promptwise hub skill"]
  hub --> mcp["MCP server (90 tools, one call_tool choke point)"]
  subgraph Capabilities
    opt[Optimization: route / compress / cache / batch]
    effort[Reasoning-effort axis: low / medium / high]
    flow[Workflow planning]
    track[Task / effort / usage tracking]
    diag[Diagram generation]
    sec[Security & compliance scanning]
    cost[Cost / budget / ROI]
    skillaudit[Skill-execution cost + audit logging]
  end
  mcp --> Capabilities
  mcp --> cap["Response-size cap (call_tool choke point)"]
  cap --> emit["Emitters: MCP · SKILL.md · AGENTS.md"]
  Capabilities --> emit
  packs[("81 skill packs")] --> mcp
  store[("SQLite ~/.promptwise")] --> Capabilities
```

Model tier (Haiku/Sonnet/Opus) and reasoning effort (low/medium/high) are two
**independent** axes — a request gets both a model recommendation and an effort
level; neither implies the other. Both axes share the same outcome-learning
design: a static heuristic first, then an optional Beta-posterior adapter that
blends in past outcomes once enough samples exist, fail-open to the static pick
on any error.

## Technical view

Modules and dependencies inside `src/promptwise/`.

```mermaid
flowchart LR
  server["server.py — call_tool choke point"] --> core
  server --> security
  server --> plugins
  server --> db
  server --> config[config.py]
  server -.every response.-> respbudget[response_budget.cap_response]
  subgraph core [core/]
    router[router]
    adaptive[adaptive_router — model-tier learning]
    effort_router[effort_router — static effort heuristic]
    effort_adapter[effort_adapter — effort learning]
    effort_map[effort_map — provider param resolution]
    rewriter[rewriter]
    optimizer[optimizer]
    compression[compression]
    workflow[workflow_planner]
    tracker[task_tracker]
    mermaid[mermaid]
    skills[skill_loader]
    audit_log[audit_log — hash-chained trace]
    respbudget
  end
  subgraph security [security/]
    scanner[scanner]
    compliance[compliance]
  end
  subgraph db [db/]
    models[models — SQLAlchemy]
  end
  router --> adaptive
  effort_router --> effort_adapter
  effort_adapter -. own sqlite table .-> models
  effort_adapter --> effort_map
  tracker --> models
  skills --> packs[("skill_packs/")]
  config --> yaml[("config/*.yaml")]
```

`response_budget.cap_response` is the single place every tool's JSON response
passes through before returning to the caller — one generic recursive walker
caps any over-limit list at any nesting depth (top-level, dict value, or list
item), with a small exempt set (`export_audit`, `get_sbom`, …) where the full
payload is the point.

## Data model (ER)

Local SQLite schema (`db/models.py`, SQLAlchemy) plus one standalone table
(`effort_outcomes`, raw sqlite3, own connection — created lazily by
`effort_adapter.py`, same database file, independent of the ORM).

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
  ROUTE_OUTCOME {
    string outcome_id PK
    string route_id
    string tier
    string quality_signal
  }
  EFFORT_OUTCOME {
    string outcome_id PK
    string task_class
    string effort
    string quality_signal
  }
```

`ROUTE_OUTCOME` (model tier) and `EFFORT_OUTCOME` (reasoning effort) feed the
two independent learning adapters — same Beta-posterior/minimum-sample design,
different ladder (Haiku→Sonnet→Opus vs. low→medium→high). Absence of history
is neutral, never negative; both adapters fail open to the static pick.

The hash-chained audit trail (`audit_log.py`) is a separate append-only
`.jsonl` file, not a database table — deliberately outside the SQLite store so
the trace survives independently of it.

## Request flow (sequence)

A `route_request` call from the agent — model tier and reasoning effort are
resolved together, each independently, both fail-open to their static pick.

```mermaid
sequenceDiagram
  participant U as Developer
  participant H as /promptwise hub
  participant M as MCP server
  participant R as Router
  participant EA as EffortAdapter
  participant D as SQLite
  U->>H: "which model, how much effort?"
  H->>M: route_request(text, budget)
  M->>R: route(text, intent, stakes)
  R-->>M: recommended_model + reason (+ adaptive blend from ROUTE_OUTCOME)
  M->>EA: _resolve_effort(intent, stakes)
  EA-->>M: effort (static, or adapted from EFFORT_OUTCOME; fail-open on error)
  M->>D: record_cost(tool, model, cost)
  M-->>H: model + effort + reason + alternatives
  H-->>U: "Use Sonnet, medium effort — reason…"
```

## Response cap (sequence)

Every tool response passes through one choke point before it reaches the
caller, regardless of shape or nesting depth.

```mermaid
sequenceDiagram
  participant H as Agent / hub
  participant CT as server.call_tool
  participant HND as tool handler
  participant CAP as response_budget.cap_response
  H->>CT: call_tool(name, arguments)
  CT->>HND: handler(ctx, arguments)
  HND-->>CT: raw JSON (unbounded)
  CT->>CAP: cap_response(name, raw_json)
  alt name in EXEMPT_TOOLS
    CAP-->>CT: unchanged (exports need the full payload)
  else over PROMPTWISE_MAX_RESPONSE_ITEMS
    CAP-->>CT: capped JSON + *_truncated_count markers, every list, every depth
  end
  CT-->>H: bounded JSON
```

## Skill invocation audit (sequence)

`invoke_skill` / `skill_chain` already computed real per-call cost and model
data; it was never persisted before this pass. Logging is additive and
fail-open — a logging failure never changes what the caller gets back.

```mermaid
sequenceDiagram
  participant H as Agent / hub
  participant M as invoke_skill / skill_chain
  participant O as Orchestrator
  participant REC as _record_skill_execution
  participant D as SQLite (cost_logs)
  participant A as AuditLog (.jsonl)
  H->>M: invoke_skill(name) / skill_chain(names)
  M->>O: execute_skill(s) [per skill, per chain step]
  O-->>M: result (status, model_used, tokens, cost_usd)
  M->>REC: for each *successful* skill result
  REC->>D: record_cost(...)  (best-effort)
  REC->>A: append(...)  (best-effort)
  Note over REC: either write failing is swallowed —<br/>caller's response is unaffected either way
  M-->>H: original response, unchanged shape
```
