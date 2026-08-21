---
name: promptwise
description: Use PromptWise to optimize prompt cost, route requests to the right model tier, plan prompt caching, rewrite/compress verbose prompts, batch small tasks, summarize long threads for handoff, scan for security/compliance issues, run governance/audit/JIT-permission workflows, plan an SDLC workflow from PromptWise's own skill packs, or invoke one of 84 role/technique skill packs. Trigger on "which model should I use", "how can I save tokens", "this prompt is too long", "cache this", "compress this context", "scan this for vulnerabilities", "how should I structure this build", "is this safe to ship", explicit cost/budget questions, or any time the user pastes a large doc.
---

# PromptWise — the cross-agent intelligence layer

PromptWise is the **intelligence + orchestration layer** for AI coding agents. It does
not replace your agent — it rides the open standards every agent already reads (MCP ·
SKILL.md · AGENTS.md) and adds what none of them have: role awareness, compliance
gating, context-budget engineering, security/governance enforcement, and workflow
planning.

When the user invokes `/promptwise` with no subcommand, show this menu, then ask
**"What would you like to optimize?"** Otherwise, pick the right tool automatically.
Tool/pack counts below reflect the current registry — if in doubt, `list_skills` and
the MCP tool list are the source of truth, not this number.

```
PromptWise — command groups (142 MCP tools · 84 skill packs):

  Optimization
  route_request        Pick the right model (Haiku/Sonnet/Opus) for a task, budget-aware
  rewrite_prompt       Strip filler, tighten, add role framing
  optimize_context     Compress large context to a token budget
  compress_prompt      Caveman compression for verbose prompts
  plan_cache           Design prompt-cache breakpoints for repeated calls
  cache_lookup/store/stats  Local result cache: exact-match first, semantic near-miss fallback when the optional [embeddings] extra is installed
  embedding_status      Local embedding provider health: installed? cached? ready? (opt-in [embeddings] extra)
  batch_prompts        Merge 2–5 small tasks into one call
  summarize_thread     Compress a long thread for fresh-chat handoff
  compare_providers    Advisory cost comparison across Claude / OpenAI / Gemini reference pricing
  check_energy         Energy-efficiency score for a model
  route_for_plugin     Detect which plugin/tool applies to a piece of text

  Prompt engineering & registry
  apply_craft            CRAFT-axis (Context/Role/Action/Format/Tone) analysis + rebuild
  inject_few_shot        Add few-shot examples to a prompt
  add_chain_of_thought    Wrap a prompt with a CoT scaffold
  chain_prompts          Decompose a complex task into a sequential prompt chain
  suggest_technique      Auto-pick CRAFT / Few-Shot / CoT / Chaining, outcome-learning informed
  eval_prompt_across_models  Cost/tier comparison for a prompt across Haiku/Sonnet/Opus
  audit_system_prompt    Score a system prompt on clarity, role, constraints, jailbreak resistance
  save_prompt / search_prompts / compare_prompts  Versioned prompt registry: save, search, diff
  rollback_prompt / replay_prompt_version  Roll back a registered prompt; replay a version through the eval harness

  Workflow planning  (PromptWise-native, the differentiator)
  plan_workflow         Classify a task → ordered chain of PromptWise skill packs (PRD → design → stories → TDD → review)
  orchestrate_tasks     Parse a multi-step prompt into a DAG and execute with a failure strategy
  run_autonomous        Autonomous developer loop (Plan → Execute → Test → Fix), policy-gated

  Agile method & governance  (agile-* personas + auditable gates)
  agile_plan             Two-phase persona plan (analyst→pm→[ux]→architect→po, then per-story sm→dev→qa)
  shard_doc               Split a PRD/architecture doc into anchored shards
  draft_story             Build a self-contained, context-engineered story
  run_quality_gate        Advisory PASS / CONCERNS / FAIL / WAIVED decision
  check_policy            Evaluate an action vs the cross-agent governance policy
  record_audit / export_audit  Append / export the hash-chained AI-change trace
  record_decision / query_decisions  ADR-style architectural decision log
  sync_agent_config        Emit one governance source → every agent's rules file (non-destructive managed blocks)
  detect_agents            Sniff a repo for configured agents (CLAUDE.md, AGENTS.md, .cursor, Copilot, Windsurf, JetBrains, Cline, Aider, Goose, OpenHands) + confidence
  build_context_model      Derive intent / role / stack / regulated context from a prompt
  propose_agent_config     Preview a per-file diff of agent rules before writing (the review step)
  lint_agent_config        Lint an agent rules file for token tax, byte caps, missing frontmatter
  check_portability        Cross-host portability check across every supported target
  export_web_bundle        Single-file governance + skill-pack bundle for ChatGPT/Gemini/Claude.ai web chat

  Security & compliance
  security_check          Pre-flight scan (secrets, injection, PII, destructive)
  prompt_injection         Detect injection / jailbreak attempts
  benchmark_injection       Benchmark the injection detector against the bundled offline corpus
  owasp_scan               OWASP Top-10 scan (10 categories)
  scan_response            Check model output for PII leaks / injection echoes / canary leaks
  run_security_suite       Full security + OWASP + framework-mapped pass
  run_red_team_harness      Offline attack/benign corpus regression gate vs a stored baseline
  review_corpus_candidates / promote_corpus_candidates  Human-reviewed injection-corpus refresh workflow
  get_sbom                 Software bill of materials (CycloneDX, transitive lockfile parsing)
  audit_mcp_servers         Audit declared MCP servers for supply-chain risk flags
  accept_risk / list_risk_register  Residual-risk register: sign off and list open findings
  export_compliance_bundle / generate_ed25519_keypair  Signed compliance evidence bundle (OWASP LLM Top 10 / NIST AI RMF / MITRE ATLAS / OWASP Agentic Top 10 / NHI Top 10 / CSA AICM / GDPR / HIPAA controls coverage)
  compliance_gap_analysis    Required-control checklist vs evidenced tools, per framework -- advisory, not a certification
  grant_jit_permission / revoke_jit_permission / list_jit_permissions  Time-boxed, scoped permission grants

  Cost, budget & ROI
  predict_cost             Estimate cost before sending
  monitor_budget            Spend vs budget limit
  set_budget_limit          Hard-stop budget in USD (advisory or hard-blocking)
  get_budget_status         Remaining budget
  budget_report             Forecast end-of-period spend, anomaly detection
  cost_report               Team cost breakdown
  session_cost_report / project_cost_report  Per-session / per-project cost rollup
  track_roi / get_roi_report  Productivity ROI, team-level report
  get_session_stats         Cost / savings / cache-hit for this session
  export_stats              Export usage history (JSON/CSV)
  export_org_report         Scheduled spend/security/governance summary for stakeholders
  check_routing_consent / grant_routing_consent  Device-scoped, ask-once routing consent

  Governance intelligence & learning
  capture_learning / replay_learnings / learning_insights  Corrections become durable, searchable rules
  insights_report           Ranked recommendations over local telemetry (routing/cost/quality/budget)
  tune_permissions           Learn allow/deny suggestions from denial telemetry
  search_trace              Search the audit trail + learnings by meaning
  rank_context              Retrieval-augmented context ranking from the trace, budget-pruned
  score_context_quality      Structure / completeness / staleness / contradiction heuristics for context shards
  context_lineage            Record or list context-shard provenance (file / MCP server / query) in the audit trail
  run_governor / governor_undo  Policy-gated, reversible autonomous governance actions + undo
  run_eval / run_eval_harness  Cost estimate / durable offline eval+regression suite
  optimize_skill_pack        Fold accumulated corrections into a skill pack (reversible managed block)

  Task / effort / token tracker
  add_task / update_task / list_tasks / task_report  Effort estimate → actual, tokens, cost rollup

  Diagrams  (Mermaid — render on GitHub & docs, no external tools)
  validate_mermaid         Lint Mermaid source before presenting
  (skill packs)            architecture-diagram · flow-diagram · er-diagram · sequence-diagram

  Roles & skill packs
  detect_role               Auto-detect organizational role
  suggest_skill              Suggest a skill pack for the request
  list_skills                List the 84 portable skill packs
  invoke_skill               Run a specific skill pack
  skill_chain                Chain multiple skill packs

  Session, memory & config
  ping_session              Record activity (reset idle clock)
  check_session_timeout      active / warn / expired
  get_memory_context         Retrieve prior-session memory
  query_memory               Search session memory (keyword-ranked; hybrid keyword+vector reranking when the optional [embeddings] extra is installed)
  clear_history              Delete records older than N days
  reload_config              Hot-reload pricing / providers / roles
  validate_output            Check generated code before presenting (heuristic + optional real linter)

Usage: describe your need and PromptWise selects the tool, or call a subcommand directly.
```

## How to choose a tool

- **Model / cost question** ("which model", "is this Opus-worthy", "save tokens") → `route_request`; add `monthly_budget_usd` if a budget was mentioned.
- **Verbose prompt** → `rewrite_prompt` (filler) or `compress_prompt` (caveman). **Long pasted doc** → `optimize_context`.
- **Repeated calls / agent loop / RAG** → `plan_cache` for cache-breakpoint design, `cache_lookup`/`cache_store` for the actual local result cache.
- **Several small tasks** → `batch_prompts`. **Thread wrapping up / near context limit** → `summarize_thread`.
- **"How should I structure this build"** → `plan_workflow` (greenfield-vs-brownfield, regulated-vs-not → an ordered chain of PromptWise's own skill packs: PRD → design → stories → TDD → review, run via `invoke_skill`). Regulated tasks graft in security-architecture + OWASP and set a compliance-gate flag. Fully self-contained — no external tools.
- **"Run the agile method / governed SDLC"** → `agile_plan` for the two-phase persona plan, then drive the `agile-*` packs; `draft_story` + `run_quality_gate` per story, `check_policy` to enforce budget/tier/gate rules, `record_audit`/`export_audit` for the trace, `sync_agent_config` to push one policy to every agent. See `docs/AGILE_METHOD.md`.
- **"Did quality drift / catch a regression"** ("eval this prompt", "regression-test my prompts", "pin expected behavior") → `run_eval_harness` on a suite of prompt+rubric cases (e.g. `config/eval_suite.json`). Runs offline, scores with the quality gate, diffs against a stored per-tier baseline, gates pass/fail, and feeds outcomes back into adaptive routing. `save_baseline: true` blesses a reviewed run.
- **Code or prompt before running** → `security_check`; deploying an app → `owasp_scan`; user-supplied prompt → `prompt_injection`; checking the injection detector itself → `benchmark_injection`; probing for gaps in the attack corpus → `run_red_team_harness`.
- **"Is this safe to ship / are we governed"** → `run_security_suite` for a full pass, `export_compliance_bundle` for signed evidence, `list_risk_register`/`accept_risk` for known residual risk, `audit_mcp_servers` for MCP supply-chain risk.
- **"We got hit / something's off"** → `create_incident` to open the case, `detect_anomalies` to check for a behavioral-baseline deviation first.
- **"Too many agents / is this agent misbehaving"** → `detect_sprawl` (capability-overlap/role duplication across the registered fleet) or `detect_agent_drift` (a specific agent's recent activity vs its registered role).
- **"Did the AI invent this package"** → `validate_dependencies`.
- **Standing exception needed** ("let me write to this file without re-asking", "trust this project for an hour") → `grant_jit_permission` (time-boxed, scoped), `list_jit_permissions` to review, `revoke_jit_permission` to pull it early.
- **Diagrams** ("draw the architecture / flow / ER / sequence") → `invoke_skill` the matching `*-diagram` pack (Mermaid out), then `validate_mermaid` before showing it.
- **Tracking a build** ("track effort / tokens", "where's the project at") → `add_task` / `update_task` / `task_report`.
- **Design help** ("which pattern", "make it faster", "solution/enterprise architecture") → `design-patterns`, `code-optimizer`, `solution-architecture`, `enterprise-architecture` packs.
- **Role/domain work** (banking, HIPAA, QA, legal, TDD, ADR, etc.) → `suggest_skill` then `invoke_skill`. The 84 packs live in `skill_packs/` and load via the MCP server.
- **Spend/ROI/budget** → the cost-&-budget group; `insights_report` for ranked recommendations across routing/cost/quality/budget.
- **"What have we decided / learned before"** → `query_decisions` for past architectural decisions, `replay_learnings`/`search_trace` for past corrections and the audit trail, `learning_insights` for correction trends.

## Cross-agent portability

The 84 skill packs in `skill_packs/` are portable `SKILL.md` files (YAML frontmatter +
prompt). Copy them into any agent's skills dir (`~/.codex/skills/`, `.cursor/skills/`,
`~/.gemini/skills/`) — same files run everywhere. `AGENTS.md` at the repo root carries
project context + the active constitution. This is the "one source, three emitters"
contract: PromptWise core → MCP tools + SKILL.md packs + AGENTS.md.
