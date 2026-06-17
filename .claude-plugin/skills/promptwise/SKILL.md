---
name: promptwise
description: Use PromptWise to optimize prompt cost, route requests to the right model tier, plan prompt caching, rewrite/compress verbose prompts, batch small tasks, summarize long threads for handoff, scan for security/compliance issues, plan an SDLC workflow from PromptWise's own skill packs, or invoke one of 72 role/technique skill packs. Trigger on "which model should I use", "how can I save tokens", "this prompt is too long", "cache this", "compress this context", "scan this for vulnerabilities", "how should I structure this build", explicit cost/budget questions, or any time the user pastes a large doc.
---

# PromptWise v1.1 — the cross-agent intelligence layer

PromptWise is the **intelligence + orchestration layer** for AI coding agents. It does
not replace your agent — it rides the open standards every agent already reads (MCP ·
SKILL.md · AGENTS.md) and adds what none of them have: role awareness, compliance
gating, context-budget engineering, and workflow planning.

When the user invokes `/promptwise` with no subcommand, show this menu, then ask
**"What would you like to optimize?"** Otherwise, pick the right tool automatically.

```
PromptWise v1.1 — command groups (65 MCP tools · 72 skill packs):

  Optimization
  route_request        Pick the right model (Haiku/Sonnet/Opus) for a task
  rewrite_prompt       Strip filler, tighten, add role framing
  optimize_context     Compress large context to a token budget
  compress_prompt      Caveman compression for verbose prompts
  plan_cache           Design prompt-cache breakpoints for repeated calls
  batch_prompts        Merge 2–5 small tasks into one call
  summarize_thread     Compress a long thread for fresh-chat handoff
  compare_providers    Compare cost across Claude / OpenAI / Gemini

  Workflow planning  (PromptWise-native, the differentiator)
  plan_workflow        Classify a task → ordered chain of PromptWise skill packs (PRD → design → stories → TDD → review)

  Agile method & governance  (agile-* personas + auditable gates)
  agile_plan           Two-phase persona plan (analyst→pm→architect→po, then per-story sm→dev→qa)
  shard_doc            Split a PRD/architecture doc into anchored shards
  draft_story          Build a self-contained, context-engineered story
  run_quality_gate     Advisory PASS / CONCERNS / FAIL / WAIVED decision
  check_policy         Evaluate an action vs the cross-agent governance policy
  record_audit         Append a hash-chained AI-change record (the "trace")
  export_audit         Export the audit trail (JSON + text) with chain verify
  sync_agent_config    Emit one governance source → every agent's rules file

  Task / effort / token tracker
  add_task             Create a task with an effort estimate
  update_task          Set status / actual hours / tokens / cost (set or increment)
  list_tasks           List tasks (optionally by status)
  task_report          Estimate-vs-actual effort, tokens, cost rollup

  Diagrams  (Mermaid — render on GitHub & docs, no external tools)
  validate_mermaid     Lint Mermaid source before presenting
  (skill packs)        architecture-diagram · flow-diagram · er-diagram · sequence-diagram

  Roles & skill packs
  detect_role          Auto-detect organizational role
  suggest_skill        Suggest a skill pack for the request
  list_skills          List the 72 portable skill packs
  invoke_skill         Run a specific skill pack
  skill_chain          Chain multiple skill packs

  Security & compliance
  security_check       Pre-flight scan (secrets, injection, PII, destructive)
  prompt_injection     Detect injection / jailbreak attempts
  owasp_scan           OWASP Top-10 scan
  scan_response        Check model output for PII leaks / injection echoes
  run_security_suite   Full security + OWASP pass
  get_sbom             Generate a software bill of materials

  Cost, budget & ROI
  predict_cost         Estimate cost before sending
  monitor_budget       Spend vs budget limit
  set_budget_limit     Hard-stop budget in USD
  get_budget_status    Remaining budget
  budget_report        Forecast end-of-period spend
  cost_report          Team cost breakdown
  track_roi            Productivity ROI
  get_session_stats    Cost / savings / cache-hit for this session
  export_stats         Export usage history (JSON/CSV)

  Session, memory & config
  ping_session         Record activity (reset idle clock)
  check_session_timeout  active / warn / expired
  get_memory_context   Retrieve prior-session memory
  query_memory         Search session memory
  clear_history        Delete records older than N days
  reload_config        Hot-reload pricing / providers / roles
  validate_output      Check generated code before presenting

Usage: describe your need and PromptWise selects the tool, or call a subcommand directly.
```

## How to choose a tool

- **Model / cost question** ("which model", "is this Opus-worthy", "save tokens") → `route_request`; add `monthly_budget_usd` if a budget was mentioned.
- **Verbose prompt** → `rewrite_prompt` (filler) or `compress_prompt` (caveman). **Long pasted doc** → `optimize_context`.
- **Repeated calls / agent loop / RAG** → `plan_cache`.
- **Several small tasks** → `batch_prompts`. **Thread wrapping up / near context limit** → `summarize_thread`.
- **"How should I structure this build"** → `plan_workflow` (greenfield-vs-brownfield, regulated-vs-not → an ordered chain of PromptWise's own skill packs: PRD → design → stories → TDD → review, run via `invoke_skill`). Regulated tasks graft in security-architecture + OWASP and set a compliance-gate flag. Fully self-contained — no external tools.
- **"Run the agile method / governed SDLC"** → `agile_plan` for the two-phase persona plan, then drive the `agile-*` packs; `draft_story` + `run_quality_gate` per story, `check_policy` to enforce budget/tier/gate rules, `record_audit`/`export_audit` for the trace, `sync_agent_config` to push one policy to every agent. See `docs/AGILE_METHOD.md`.
- **Code or prompt before running** → `security_check`; deploying an app → `owasp_scan`; user-supplied prompt → `prompt_injection`.
- **Diagrams** ("draw the architecture / flow / ER / sequence") → `invoke_skill` the matching `*-diagram` pack (Mermaid out), then `validate_mermaid` before showing it.
- **Tracking a build** ("track effort / tokens", "where's the project at") → `add_task` / `update_task` / `task_report`.
- **Design help** ("which pattern", "make it faster", "solution/enterprise architecture") → `design-patterns`, `code-optimizer`, `solution-architecture`, `enterprise-architecture` packs.
- **Role/domain work** (banking, HIPAA, QA, legal, TDD, ADR, etc.) → `suggest_skill` then `invoke_skill`. The 72 packs live in `skill_packs/` and load via the MCP server.
- **Spend/ROI/budget** → the cost-&-budget group.

## Cross-agent portability

The 72 skill packs in `skill_packs/` are portable `SKILL.md` files (YAML frontmatter +
prompt). Copy them into any agent's skills dir (`~/.codex/skills/`, `.cursor/skills/`,
`~/.gemini/skills/`) — same files run everywhere. `AGENTS.md` at the repo root carries
project context + the active constitution. This is the "one source, three emitters"
contract: PromptWise core → MCP tools + SKILL.md packs + AGENTS.md.
