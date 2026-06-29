# Changelog

All notable changes to PromptWise are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to adhere to
semantic versioning.

## [1.2.0] — Enforcement layer & feature-gap build

Turns governance from something the agent *opts into* into something it *can't avoid*,
built additively — no existing behavior removed.

### Added
- **Runtime enforcement hooks (`hooks/` + `core/hook_bridge.py`).** A Claude Code
  lifecycle-hooks layer that auto-invokes PromptWise's existing engines and can block:
  - `UserPromptSubmit` → policy + injection scan before work begins
  - `PreToolUse(Write|Edit)` → secret / destructive / injection scan (blocks the write)
  - `PreToolUse(any)` → per-session tool-call budget (curbs runaway loops)
  - `PostToolUse(Write|Edit)` → hash-chained audit record (the trace)
  - `Stop` → advisory quality-gate decision
  - `SessionEnd` → export the portable trace
  - Fail-open by design: a hook error never wedges the session. Stdlib only; state is
    project-local under `.promptwise/`. No external infra, no MCP process spawned.
- **Continuous learning loop** (`capture_learning`, `replay_learnings`,
  `learning_insights`). Corrections become durable, FTS5-searchable, replayable rules.
  Local SQLite with a transparent LIKE fallback. Offline.
- **Offline skill auto-optimization** (`optimize_skill_pack`). Folds accumulated
  corrections into a SKILL.md as a stamped, reversible managed block, accepting a patch
  only when a deterministic quality score strictly improves. No LLM required.
- **Policy intelligence & searchable trace** (`tune_permissions`, `audit_mcp_servers`,
  `search_trace`). Learn allow/deny rules from denial telemetry; audit the MCP supply
  chain for risk and redundancy; search the audit trail + learnings by meaning. All
  offline (optional local embeddings, keyword/FTS fallback).
- Plugin surface: slash commands (`commands/`) and a governance-reviewer sub-agent
  (`agents/`); new skill packs — `llm-council`, `deslop`, `thoroughness`,
  `token-efficiency`, `compact-guard`.
- `SECURITY.md` and this changelog.

### Fixed
- `core/router.py`: import `ProviderConfig` (latent `NameError` when a provider key
  existed in `config.providers`).
- `security/scanner.py`: detect spaced secret assignments (`API_KEY = "sk-…"`), the
  most common real form, which the prior regex missed (additive — no detections lost).
- `core/cache_planner.py`: enforce the provider minimum cacheable-prefix length (1024
  tok, 2048 for Haiku), fix the cacheable-span to count the prefix `[0..i]` inclusive
  (the common large-system case previously computed 0 cacheable tokens and never
  cached), and report real net-dollar savings instead of a fixed heuristic.
- `db/models.py`: `save_fact` upserts by `(key, scope)` instead of piling duplicate
  rows; `query_facts` / `search_prompts` rank by relevance and recency.

### Counts
- MCP tools: 69 → **76**. Skill packs: 72 → **77**. README, `plugin.json`, and
  `marketplace.json` reconciled to these numbers.

## [1.1.0]
- Cross-agent config compiler (CLAUDE.md / AGENTS.md / .cursor / Copilot), governed
  agile method (personas, quality gates, policy-as-code, hash-chained audit), workflow
  planner, 72 skill packs, diagrams, and task tracking.
