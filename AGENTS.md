# AGENTS.md — PromptWise

Universal project-context file for AI coding agents (the open standard that supersedes
agent-specific files like CLAUDE.md / .cursorrules). Any agent that reads `AGENTS.md`
gets this context.

## What this project is

PromptWise is a **cross-agent intelligence layer** for AI coding agents. It rides three
open standards — **MCP**, **SKILL.md**, **AGENTS.md** — and adds role awareness, model
routing, cost/budget control, security & compliance scanning, and framework
orchestration. It is a conductor, not a replacement for your agent.

## Architecture (one source, three emitters)

```
PromptWise core  (router · roles · compliance · context engine · framework_router)
        ├─▶ MCP tools      → route_request, recommend_framework, owasp_scan, …  (60+)
        ├─▶ SKILL.md packs → 55 portable role/technique packs in skill_packs/
        └─▶ AGENTS.md      → this file: project context + active constitution
```

- Engine: `src/promptwise_v3/` (MCP server in `server.py`, logic in `core/`, `security/`, `plugins/`).
- Skill packs: `skill_packs/` — portable `SKILL.md` files, loaded by the MCP `SkillLoader`.
- Config: `config/promptwise_v3.yaml` (pricing, providers, roles, security, skills dir).

## Constitution (compliance gate — non-negotiable rules)

Regulated work (banking, HIPAA, FINRA, GDPR, PCI, legal) MUST keep an auditable artifact
chain: PRD → architecture → stories → commit. `recommend_framework` flags regulated
tasks with `compliance_gate: true` and routes them to a spec-driven framework whose
constitution.md is the activation point. Do not strip audit trails on regulated tasks.

## How an agent should use PromptWise

1. Cost/model decisions → call `route_request` before sending large/complex prompts.
2. Structuring a build → call `recommend_framework` to pick BMAD / Spec Kit / OpenSpec / TaskMaster.
3. Domain work → `suggest_skill` then `invoke_skill` from the 55 packs.
4. Before running code or deploying → `security_check` / `owasp_scan`.
5. Long sessions → `summarize_thread` and `plan_cache` to control token spend.

## Conventions

- Python ≥ 3.10. Engine is self-contained (no network required for routing/scanning).
- Keep skill packs as `SKILL.md` with YAML frontmatter (`name`, `description`, `triggers`,
  `roles`, `model_tier`) so they stay portable across agents.
