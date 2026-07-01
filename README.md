# PromptWise

**The governance & intelligence layer for AI agents.** Role-aware prompting, model
routing, cost & budget control, security/compliance scanning, responsible-AI advisories,
workflow planning, a governed agile method, runtime enforcement hooks, and 80 portable skill
packs — emitted in the formats every agent already reads.

> Built on open standards, not against them. PromptWise is a *conductor*, not a replacement
> for Cursor / Copilot / Claude Code.

**Works with:** Claude Code · Codex · Cursor · Gemini CLI · Copilot · any MCP host
**Standards:** MCP · SKILL.md · AGENTS.md

[![CI](https://github.com/u2anilgit/PromptWise/actions/workflows/ci.yml/badge.svg)](https://github.com/u2anilgit/PromptWise/actions/workflows/ci.yml)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Skill packs](https://img.shields.io/badge/skill%20packs-80-7C5BD4.svg)
![MCP tools](https://img.shields.io/badge/MCP%20tools-76-4C5BD4.svg)

📖 **[User Guide](docs/USER_GUIDE.md)** · [Install](INSTALL.md) · [Configuration](CONFIGURATION.md) · [Architecture](docs/ARCHITECTURE.md)

---

## Why

The ecosystem standardized. MCP (Linux Foundation–governed), SKILL.md, and AGENTS.md are
now the shared substrate across every major coding agent. PromptWise doesn't fight that —
it compiles its intelligence **down to those three formats** and adds the layer none of
them have:

- **Model routing** — right tier (Haiku/Sonnet/Opus) per task, with budget awareness.
- **Context-budget engineering** — compression, caching, batching, thread handoff.
- **Role intelligence** — 80 role/technique skill packs (banking, HIPAA, QA, TDD, ADR, …).
- **Compliance gating** — auditable PRD→architecture→story→commit chain for regulated teams.
- **Runtime enforcement** — Claude Code lifecycle hooks auto-run security/policy/audit checks and can *block* (secret writes, runaway loops), turning advisory governance into enforced governance. Fail-open: a hook error never wedges the session. See `hooks/`.
- **Continuous learning** — corrections become durable, searchable rules (FTS5) replayed before relevant work; packs self-optimize offline. Local-first, air-gapped safe.
- **Workflow planning** — classify a task → an ordered chain of PromptWise's *own* skill packs (PRD → design → stories → TDD → review). Fully self-contained, no external tools.
- **Governed agile method** — analyst→pm→architect→po planning then per-story sm→dev→qa loop, with context-engineered stories, advisory quality gates, policy-as-code, and a hash-chained audit trail. See [docs/AGILE_METHOD.md](docs/AGILE_METHOD.md).

## Architecture — one source, three emitters

```
PromptWise core  (router · roles · compliance · context engine · workflow_planner)
        ├─▶ MCP tools      → route_request, plan_workflow, owasp_scan …  (76)
        ├─▶ SKILL.md packs → 80 portable packs in skill_packs/
        ├─▶ Lifecycle hooks→ enforce security/policy/audit at runtime (hooks/)
        └─▶ AGENTS.md      → project context + active constitution
```

## Quickstart (Claude Code)

```bash
git clone https://github.com/u2anilgit/PromptWise.git
cd PromptWise
pip install -e .
```

Add the plugin marketplace (local) and enable it, or point your MCP host at the server:

```jsonc
// .mcp.json — already included
{
  "mcpServers": {
    "promptwise": {
      "command": "python",
      "args": ["-m", "promptwise.server"],
      "cwd": "${projectDir}",
      "env": { "PYTHONPATH": "${projectDir}/src" }
    }
  }
}
```

Restart your agent, run `/mcp` — PromptWise tools appear. Then just `/promptwise`.

## What's inside

| Path | What |
|------|------|
| `src/promptwise/` | Engine: MCP server + core logic, security, plugins, transports |
| `skill_packs/` | 80 portable `SKILL.md` role/technique packs (incl. `agile/` personas; copy into any agent) |
| `hooks/` | Claude Code lifecycle hooks — runtime security/policy/audit enforcement (fail-open) |
| `commands/`, `agents/` | Plugin slash commands and sub-agents |
| `.claude-plugin/` | Plugin + marketplace manifests, the `/promptwise` hub skill |
| `config/` | Pricing, providers, roles, security, compliance config |
| `AGENTS.md` | Universal project-context emitter |
| `docs/` | Integration guides (configuration reference, multi-platform setup) |

## Workflow planner (self-contained)

`plan_workflow` classifies a task by intent · scale · risk and returns an ordered chain
of PromptWise's **own** skill packs — each step runnable via `invoke_skill`. No external
frameworks, CLIs, or network:

| Task shape | → Workflow (PromptWise skill packs) |
|------------|-------------------------------------|
| Greenfield build | `prd-generator` → `system-design` → `user-story-generator` → `tdd` → `code-review` → `verification-before-completion` |
| Brownfield change | `systematic-debugging` → `refactoring` → `test-generator` → `code-review` → `verify` |
| Docs / spec only | `prd-generator` → `user-story-generator` → `adr` |
| Regulated (any of the above) | + `security-architecture` + `owasp_scan` + `get_sbom`, compliance-gate flag set |

## Documentation

| Doc | What |
|-----|------|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Hands-on: hub, working with skills, real examples |
| [INSTALL.md](INSTALL.md) | Install + register with any MCP host |
| [CONFIGURATION.md](CONFIGURATION.md) | Config files, budgets, security, adding packs |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Functional / technical / ER / sequence diagrams |

## Testing

```bash
pip install -e ".[dev]"
python -m pytest tests -q        # packs, planner, agile method, governance, enforcement hooks, learning loop, policy intel, tracker, tools
```

## Status

**Early-stage, building in public.** v1.2 ships the engine, the five emitters, the 80
skill packs (incl. the `agile/` method personas), the self-contained workflow planner, the
governed agile method (quality gates, policy-as-code, hash-chained audit trail), the runtime
enforcement hooks layer, a continuous learning loop with offline skill auto-optimization,
MCP supply-chain auditing, a searchable trace, diagram generators, and a task/effort/token
tracker. Everything runs directly from PromptWise — local-first, no third-party integrations.

## License

MIT — see [LICENSE](LICENSE). Open standards are credited in [NOTICE](NOTICE).
