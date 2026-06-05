# PromptWise v3.0 — Design Spec

**Date:** 2026-06-03  
**Approach:** Hook-First (Approach B)  
**Scope:** Individual-first local install → Team → Enterprise  
**Baseline:** v2.0 engine (24 MCP tools, 7 core modules, 4 plugins) — zero breaking changes

---

## 1. Goals

1. Ship autonomous skill chains (WOW moment) by week 3 — type "build this feature" → full pipeline runs
2. Cover all real-world business problem categories: dev workflow, security, knowledge mgmt, docs, testing, automation, FinOps, team collaboration, enterprise compliance
3. Single `model_strategy.yaml` file controls all model routing — safe + cost-optimized across all 49 tools and 45 skills
4. Progressive tiers: Phases 0–5 complete a full individual install; Phases 6–7 add team/enterprise without rewrites

---

## 2. Architecture

### 2.1 Core principles

- **Skill format:** `.md` files with YAML frontmatter (same pattern as `skills/promptwise/SKILL.md`)
- **No breaking changes:** v1 and v2 tools preserved; new tools/skills additive only
- **Orchestrator upgrade:** real Claude API execution replaces text-split DAG; old `execute()` stays for backward compat
- **DB path:** SQLite (individual, zero config) → PostgreSQL (team/enterprise) via SQLAlchemy ORM; config flag switches backend
- **Security:** levels 1–5 existing; levels 6–9 added in Phase 2 — runs on every request pre-LLM

### 2.2 Directory structure (target state)

```
src/promptwise_v2/
  core/
    orchestrator.py       ← upgraded: execute_skill() + execute_skill_chain()
    skill_loader.py       ← NEW: scans skills/, parses frontmatter, indexes triggers
    skill_validator.py    ← NEW: jsonschema output schema validation
    quality_guard.py      ← NEW: confidence scoring + hallucination signal
    automation_engine.py  ← NEW Phase 5: APScheduler triggers
    audit_logger.py       ← NEW Phase 7: append-only compliance log
    router_v2.py          ← upgraded: reads model_strategy.yaml
    security.py           ← upgraded: levels 1-5 existing + 6-9 new
    memory_manager.py     ← upgraded: SQLAlchemy ORM, team fields
    compression_engine.py ← unchanged
    context_engine.py     ← unchanged
    role_intelligence.py  ← unchanged
  skills/
    dev/                  ← Phase 1 (8 skills)
    security/             ← Phase 2 (7 skills)
    knowledge/            ← Phase 3 (7 skills)
    docs/                 ← Phase 4 (9 skills)
    testing/              ← Phase 4 (5 skills)
    automation/           ← Phase 5 (3 skills)
    team/                 ← Phase 6 (4 skills)
    enterprise/           ← Phase 7 (2 skills)
  plugins/
    budget_guardian.py    ← upgraded: project_id tagging, cost anomaly detection
    roi_tracker.py        ← unchanged
    monitoring.py         ← upgraded: model efficiency ratio
  dashboard/
    finops_dashboard.py   ← NEW Phase 5: burn rate, anomaly, forecast
    web_dashboard.py      ← upgraded Phase 7: admin UI, audit log viewer
  integrations/
    mcp_server_v2.py      ← upgraded each phase: new tools registered here
  db/
    models.py             ← NEW: SQLAlchemy ORM models
    migrations/           ← NEW: Alembic migration scripts
config/
  promptwise_v2.yaml      ← existing, extended each phase
  model_strategy.yaml     ← NEW Phase 0: all model routing rules
```

### 2.3 Skill frontmatter schema

Every skill `.md` file uses this contract:

```yaml
---
name: string              # kebab-case, unique skill ID
description: string       # used for auto-trigger matching + list_skills output
triggers: string[]        # keywords matched by skill_loader against user prompt
depends_on: string[]      # skills that must run before this one (DAG)
output_schema:            # jsonschema — validated before handoff to next skill
  type: object
  properties: {}
roles: string[]           # IT | Dev | EM | PM | SM | NTM (enforced by role_intelligence.py)
model_tier: string        # opus | sonnet | haiku | auto (auto = model_strategy.yaml decides)
---
```

### 2.4 model_strategy.yaml (Phase 0)

Single file controls all model routing:

```yaml
default_model: claude-sonnet-4-6

routing_rules:
  opus:
    skills: [systematic-debugging, system-design, architecture-review,
             security-architecture, agent-chain-designer, system-prompt-auditor,
             rag-optimizer, multi-model-eval, e2e-test-designer]
    extended_thinking_tokens: 8000

  haiku:
    skills: [verification-before-completion, git-workflow, changelog-generator,
             test-coverage-advisor, pii-detector, injection-detector,
             user-story-generator, prompt-registry, sbom-generator,
             license-compliance, ping_session, check_session_timeout]

  sonnet:
    skills: [tdd, code-review, refactoring, feature-dev, test-generator,
             api-docs, brd-generator, prd-generator, api-testing,
             few-shot-builder, model-migration-advisor, secrets-rotation-advisor,
             test-data-generator, owasp-checker, adr]

cost_safety:
  downgrade_at_budget_pct: 80     # opus → sonnet at 80% budget
  emergency_haiku_pct: 95         # all → haiku at 95% budget
  hard_stop_pct: 100
  never_downgrade:                # safety-critical — never cost-downgraded
    - security-architecture
    - systematic-debugging
    - pii-detector
    - injection-detector

context_routing:
  large_context_threshold: 50000  # tokens
  large_context_model: claude-sonnet-4-6

skill_chain_optimization:
  parallel_capable:               # run in parallel inside chains
    - pii-detector
    - injection-detector
    - owasp-checker
  max_parallel: 3
```

Hot-reloaded via existing `reload_config` MCP tool — no restart required.

### 2.5 3 new MCP tools (Phase 0)

| Tool | Inputs | Behaviour |
|------|--------|-----------|
| `invoke_skill` | `skill_name, context, params` | Load skill .md → route model → execute via upgraded orchestrator → validate output_schema → store in memory |
| `list_skills` | `category?, role?` | Scan skills/, parse frontmatter, filter by role_intelligence current role, return JSON |
| `skill_chain` | `skills[], mode, context` | Build DAG from depends_on, run sequential or parallel, validate typed handoffs between skills, handle failures per strategy |

---

## 3. Phase Specifications

### Phase 0 — Foundation + Engine (Week 1–2)

**Deliverables:**
- `core/skill_loader.py` — startup scan of `skills/`, YAML frontmatter parser, trigger keyword indexer (confidence >0.6 auto-suggest)
- `core/skill_validator.py` — jsonschema validation of skill output before chain handoff
- `core/quality_guard.py` — post-generation confidence scoring (Haiku) + hallucination signal check
- `core/orchestrator.py` upgrade — `execute_skill()` + `execute_skill_chain()` methods added; old `execute()` preserved
- `core/router_v2.py` upgrade — reads `model_strategy.yaml`, applies cost_safety rules, resolves final model per request
- `config/model_strategy.yaml` — initial routing rules for all known skills
- `mcp_server_v2.py` — registers `invoke_skill`, `list_skills`, `skill_chain` (24 → 28 tools)
- `plugins/budget_guardian.py` upgrade — `project_id` tagging, cost anomaly detection (>2× 7-day avg = alert)
- New MCP tool: `cost_report(project_id?, period?, format?)` (28 → 29 tools)
- New YAML config keys: `quality.confidence_threshold`, `quality.enabled`, `storage.backend`

**Key implementation details:**
- `execute_skill()` calls `anthropic.messages.create()` async; uses `asyncio` throughout
- `SkillLoader.auto_suggest()` hooks into existing plugin_system.py detection pipeline
- `QualityGuard.check()` runs as post-generation middleware — skippable via config
- `project_id` passed as optional param to all MCP tools; stored on every skill_run record

---

### Phase 1 — Dev Workflow Skills (Week 2–3)

**8 skills** in `skills/dev/`:

| Skill | Model | Chain role |
|-------|-------|-----------|
| `tdd` | Sonnet | Write failing tests before implementation |
| `systematic-debugging` | Opus+thinking | Reproduce → isolate → hypothesize → verify |
| `feature-dev` | auto | Orchestrator skill: chains brainstorm→tdd→code-review→verification |
| `code-review` | Sonnet | Structured review JSON: `{issues, score, approved, suggestions}` |
| `verification-before-completion` | Haiku | Checklist: tests pass, no TODOs, docs updated, security clear |
| `refactoring` | Sonnet | Characterization tests first → refactor one concern at a time |
| `git-workflow` | Haiku | Conventional commits, PR descriptions, branch naming |
| `finishing-branch` | Sonnet | Pre-merge gate: review + verification + git-workflow |

**Autonomous chain (the WOW moment):**
```
User: "build this feature: [description]"
  → skill_chain([tdd, feature-dev, code-review, verification-before-completion])
  → each step's output_schema validated before handoff
  → final output: {implementation_files, test_files, review_summary, verified: true}
```
Note: requirements clarification (brainstorming) uses the existing `superpowers:brainstorming` Claude Code skill before the chain — it is not a new PromptWise skill.

No new Python modules needed — Phase 0 infrastructure handles execution.

---

### Phase 2 — Security Hardening (Week 4–6)

**security.py upgrade:** levels 1–5 (existing regex) + 4 new levels:

| Level | Name | Implementation |
|-------|------|---------------|
| 6 | PII detector | Regex fast-path (email/SSN/CC/phone) + Haiku classifier; action: redact/warn/block (config) |
| 7 | Prompt injection | Pattern library (DAN, ignore-previous, act-as, developer-mode) + Haiku confidence; block >0.7 |
| 8 | CVE lookup | OSV.dev API (`https://api.osv.dev/v1/query`); reads requirements.txt/package.json/go.mod/pom.xml/Cargo.toml; 24hr SQLite cache |
| 9 | SBOM + license | CycloneDX 1.5 JSON from lock files; SPDX compatibility matrix (MIT/Apache/BSD vs GPL/AGPL/LGPL) |

**7 skills** in `skills/security/`: `pii-detector`, `injection-detector`, `owasp-checker`, `cve-lookup`, `license-compliance`, `sbom-generator`, `secrets-rotation-advisor`

**New MCP tools (2):** `run_security_suite(targets?)`, `get_sbom(format?)` (29 → 31 tools)

**New YAML config keys:**
```yaml
security:
  pii_detection: true
  pii_action: warn           # redact | warn | block
  injection_detection: true
  injection_threshold: 0.7
  owasp_check: post_generation
  cve_cache_ttl_hours: 24
  license_policy: permissive  # permissive | copyleft-warn | copyleft-block
```

---

### Phase 3 — Knowledge Management + AI/Prompt Engineering (Week 6–8)

**Prompt registry** — extends `memory_manager.py`:

```sql
CREATE TABLE prompts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  content TEXT NOT NULL,
  tags TEXT,              -- JSON array
  version INTEGER DEFAULT 1,
  parent_id TEXT,         -- versioning chain
  embedding BLOB,         -- for semantic search
  created_ts REAL,
  used_count INTEGER DEFAULT 0,
  project_id TEXT,
  visibility TEXT DEFAULT 'private'  -- private | team | public (Phase 6)
);
```

**2 new MCP tools:** `save_prompt(name, content, tags?)`, `search_prompts(query, limit?)` (31 → 33 tools)

**7 skills** in `skills/knowledge/`:

| Skill | Model | Key detail |
|-------|-------|-----------|
| `prompt-registry` | Haiku | Save/version/tag/search; embeddings via `sentence-transformers` (local, free, no API cost); semantic search via cosine similarity |
| `multi-model-eval` | Opus-judge | Parallel `asyncio.gather()` across Opus/Sonnet/Haiku; Opus scores each on structured rubric |
| `few-shot-builder` | Sonnet | Selects diverse examples from registry; generates synthetic examples for coverage gaps |
| `rag-optimizer` | Opus | Reviews chunk size/overlap/retrieval; uses context_engine.py internals as reference |
| `agent-chain-designer` | Opus | Maps task → skill DAG; outputs ready-to-run `skill_chain()` call + Mermaid flowchart |
| `system-prompt-auditor` | Opus+thinking(5000) | Adversarial red-team; checks against injection-detector patterns |
| `model-migration-advisor` | Sonnet | Migration checklist; chains with multi-model-eval to test prompts on target model |

---

### Phase 4 — Docs + Testing Skills (Week 8–11)

**9 docs skills** in `skills/docs/` — all role-gated:

| Skill | Role | Model | Output format |
|-------|------|-------|--------------|
| `brd-generator` | PM/BA | Opus | Markdown + DOCX (python-docx) |
| `prd-generator` | PM | Sonnet | Markdown with embedded user stories |
| `user-story-generator` | PM/SM | Haiku | JSON story array with acceptance criteria |
| `system-design` | Architect | Opus | Mermaid C4 diagram + ADR Markdown |
| `adr` | Architect | Sonnet | MADR format; auto-committed via git-workflow skill |
| `architecture-review` | Architect/EM | Opus | Scored review JSON |
| `security-architecture` | Architect/IT | Opus | STRIDE threat model Markdown |
| `api-docs` | Dev | Sonnet | OpenAPI 3.1 YAML + Markdown |
| `changelog-generator` | Dev/SM | Haiku | Keep-a-Changelog from git log |

**5 testing skills** in `skills/testing/`:

| Skill | Model | Key integration |
|-------|-------|----------------|
| `test-generator` | Sonnet | pytest/jest/go detection; AAA pattern; reads source via context_engine |
| `test-coverage-advisor` | Haiku | coverage.xml/lcov.info/cover.out; ranks gaps by cyclomatic complexity; chains to test-generator |
| `api-testing` | Sonnet | Reads output of api-docs skill; generates pytest + Postman collection |
| `e2e-test-designer` | Opus | Wraps existing playwright_bridge.py; adds Opus-level journey scenario design |
| `test-data-generator` | Sonnet | SQLAlchemy/Pydantic/TypeScript schema → JSON fixtures/CSV/SQL INSERT; Faker for PII-safe data |

No new MCP tools needed — `invoke_skill` and `skill_chain` from Phase 0 handle all 14 skills.

---

### Phase 5 — Workflow Automation + FinOps Dashboard (Week 11–13)

**Automation engine** — new `core/automation_engine.py`:

```python
# Trigger types:
# - cron:       APScheduler cron expression
# - webhook:    POST /trigger/{chain_name} on Flask server
# - file_watch: watchdog monitors path patterns
# - event:      internal events (budget_alert, security_finding, cve_detected)
#
# Each trigger stores a skill_chain() call definition in SQLite
# Execution result stored in memory_manager, notification sent per notify config
```

**Trigger definition** (user-created YAML):
```yaml
name: daily-security
trigger: cron
schedule: "0 9 * * *"
chain: [sbom-generator, cve-lookup, license-compliance]
notify: cli    # cli | webhook (Phase 6 adds slack | teams)
```

**3 new MCP tools:** `create_trigger(name, trigger_type, chain, schedule?)`, `list_triggers()`, `delete_trigger(id)` (33 → 36 tools)

**3 automation skills** in `skills/automation/`:
- `scheduled-scan` — template for recurring security/quality scans
- `auto-changelog` — triggers on git push, runs changelog-generator, commits result
- `budget-watchdog` — event-triggered: fires cost_report + alert when anomaly detected

**FinOps Dashboard** — new `dashboard/finops_dashboard.py`:
- Per-project cost breakdown (uses project_id from Phase 0)
- Terminal sparklines for daily/weekly burn rate
- Cost anomaly alert (>2× 7-day rolling average)
- Model efficiency ratio: `quality_score / cost_usd` (data from multi-model-eval runs)
- Budget forecast: linear regression on daily_burn → "exhausted in N days"
- Export: JSON/CSV

---

### Phase 6 — Team Edition (Week 13–16)

**Guiding principle:** Phases 0–5 unchanged. Team layer adds shared state + notifications only.

**Backend upgrade** — `db/models.py` (SQLAlchemy ORM):
- All tables gain `org_id`, `user_id`, `team_id` fields
- `storage.backend: postgresql` in config switches from SQLite to PostgreSQL
- Alembic migrations handle schema evolution

**Team features:**

| Feature | Implementation |
|---------|---------------|
| Shared prompt library | `prompts.visibility = team/public`; team members search each other's prompts |
| Team budgets | `budget_guardian` aggregates by `team_id`; per-user spend rollup |
| Per-user cost attribution | `user_id` tagged on every skill_run, MCP call |
| Slack/Teams notifications | Webhook endpoint in `web_dashboard.py`; fires on: skill complete, budget alert, CVE detected, security finding |
| GitHub Actions | `promptwise-action/action.yml` — runs security_check + code-review + verification as pre-merge gate |
| Prometheus | `/metrics` endpoint via `prometheus_client`: cost_per_step, burn_rate, model_distribution, skill_invocations, quality_scores |

**8 new MCP tools** (36 → 44): `invite_user`, `set_team_budget`, `get_team_stats`, `share_prompt`, `list_team_prompts`, `create_webhook`, `get_prometheus_metrics`, `github_action_status`

**4 skills** in `skills/team/`:
- `team-prompt-sync` — push/pull from shared registry with conflict resolution
- `cost-allocation-report` — per-user/per-project CSV for finance
- `onboarding-guide` — generates team-specific setup guide from org's skill library
- `skill-usage-analytics` — which skills used most/least, by whom, at what cost

---

### Phase 7 — Enterprise Edition (Week 16–21)

**Identity + access:**
```
SSO:  OAuth2 / SAML via Authlib
RBAC: viewer / member / admin tiers
      Per-skill frontmatter: roles: [Dev, IT] enforced by role_intelligence.py + token context
```

**Compliance + audit trail** — new `core/audit_logger.py`:
- Append-only log; every MCP tool call recorded with full context
- GDPR: `gdpr_delete(user_id)` wipes all user data across all tables
- SOC2 signals: structured JSON logs compatible with Splunk/Datadog/CloudWatch

**VS Code Extension:**
- Wraps existing MCP + Flask server — no new Python
- Auto-starts on workspace open
- All MCP tools as VS Code commands (`Ctrl+Shift+P → PromptWise: Invoke Skill`)
- Status bar: live cost + active model
- Per-workspace `model_strategy.yaml` overrides

**Multi-tenant:**
- `org_id` isolation across all tables
- Per-tenant `promptwise_v2.yaml` overrides: model limits, approved skill list, budget caps
- Admin dashboard: extends existing Flask `web_dashboard.py` — org stats, user management, audit log viewer

**5 new MCP tools** (44 → 49): `sso_login`, `rbac_check`, `audit_log_query`, `gdpr_delete`, `tenant_config`

**2 skills** in `skills/enterprise/`:
- `compliance-report` — generates SOC2/GDPR-ready usage report
- `access-review` — periodic RBAC review: who has access to what, flag stale permissions

---

## 4. Tool + Skill Count by Phase

| Phase | Version | MCP Tools | Skills | Cumulative Tools | Cumulative Skills |
|-------|---------|-----------|--------|-----------------|-------------------|
| Baseline | v2.0 | +0 | +0 | 24 | 0 |
| Phase 0 | v3.0 | +5 | 0 | 29 | 0 |
| Phase 1 | v3.1 | +0 | +8 | 29 | 8 |
| Phase 2 | v3.2 | +2 | +7 | 31 | 15 |
| Phase 3 | v3.3 | +2 | +7 | 33 | 22 |
| Phase 4 | v3.4 | +0 | +14 | 33 | 36 |
| Phase 5 | v3.5 | +3 | +3 | 36 | 39 |
| **Individual complete** | **v3.5** | — | — | **36** | **39** |
| Phase 6 | v3.6 | +8 | +4 | 44 | 43 |
| Phase 7 | v3.7 | +5 | +2 | 49 | 45 |
| **Total** | **v3.7** | — | — | **49** | **45** |

---

## 5. Dependencies

```
Python:   anthropic, mcp, fastapi/flask, sqlalchemy, alembic, apscheduler,
          watchdog, jsonschema, python-frontmatter, httpx, faker,
          python-docx, prometheus_client, authlib, sentence-transformers,
          numpy, pytest
Node:     (VS Code extension only) vscode API
External: OSV.dev API (free, public), Anthropic API
Optional: PostgreSQL (team+), Prometheus (team+), Slack/Teams webhooks (team+)
```

---

## 6. What this does NOT include

- Any changes to v1 modules (`promptwise/` package) — preserved exactly
- Existing v2 MCP tools — all 24 preserved, no signature changes
- `context_engine.py`, `compression_engine.py` — reused unchanged
- Mobile clients, browser extension, or any frontend beyond existing Flask dashboard
- LLM providers other than Anthropic (multi-provider comparison exists as skill, not as execution backend)
