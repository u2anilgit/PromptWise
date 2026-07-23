# PromptWise

**The governance & intelligence layer for AI agents.** Role-aware prompting, model
routing, cost & budget control, security/compliance scanning, responsible-AI advisories,
workflow planning, a governed agile method, runtime enforcement hooks, and 81 portable skill
packs — emitted in the formats every agent already reads.

> Built on open standards, not against them. PromptWise is a *conductor*, not a replacement
> for Cursor / Copilot / Claude Code.

**Works with:** Claude Code · Codex · Cursor · Gemini CLI · Copilot · any MCP host
**Standards:** MCP · SKILL.md · AGENTS.md

[![CI](https://github.com/u2anilgit/PromptWise/actions/workflows/ci.yml/badge.svg)](https://github.com/u2anilgit/PromptWise/actions/workflows/ci.yml)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Skill packs](https://img.shields.io/badge/skill%20packs-81-7C5BD4.svg)
![MCP tools](https://img.shields.io/badge/MCP%20tools-90-4C5BD4.svg)

📖 **[User Guide](docs/USER_GUIDE.md)** · [Install](INSTALL.md) · [Configuration](CONFIGURATION.md) · [Architecture](docs/ARCHITECTURE.md)

---

## Why

The ecosystem standardized. MCP (Linux Foundation–governed), SKILL.md, and AGENTS.md are
now the shared substrate across every major coding agent. PromptWise doesn't fight that —
it compiles its intelligence **down to those three formats** and adds the layer none of
them have:

- **Model routing** — right tier (Haiku/Sonnet/Opus) per task, with budget awareness.
- **Reasoning-effort routing** — low/medium/high, independent of model tier — plus an
  outcome-learning adapter (mirrors the model-tier router's design) that blends in past
  results once there's enough evidence, fail-open to the static pick otherwise.
- **Context-budget engineering** — compression, caching, batching, thread handoff.
- **Response-size governance** — every tool response passes through one size cap at the
  `call_tool` choke point before reaching the caller; a generic recursive walker bounds
  any over-limit list at any nesting depth, exempting the handful of tools (exports) where
  the full payload is the point.
- **Role intelligence** — 81 role/technique skill packs (banking, HIPAA, QA, TDD, ADR, …).
- **Compliance gating** — auditable PRD→architecture→story→commit chain for regulated teams.
- **Runtime enforcement** — Claude Code lifecycle hooks auto-run security/policy/audit checks and can *block* (secret writes, runaway loops), turning advisory governance into enforced governance. Fail-open: a hook error never wedges the session. See `hooks/`.
- **Red-team regression harness** — a durable, offline attack/benign corpus run against the security scanner, diffed against a stored baseline to catch both missed detections and false-positive regressions (`run_red_team_harness`). All scanning is air-gapped by default — no unconditional network calls.
- **Continuous learning** — corrections become durable, searchable rules (FTS5) replayed before relevant work; packs self-optimize offline. Local-first, air-gapped safe.
- **Workflow planning** — classify a task → an ordered chain of PromptWise's *own* skill packs (PRD → design → stories → TDD → review). Fully self-contained, no external tools.
- **Governed agile method** — analyst→pm→architect→po planning then per-story sm→dev→qa loop, with context-engineered stories, advisory quality gates, policy-as-code, and a hash-chained audit trail. See [docs/AGILE_METHOD.md](docs/AGILE_METHOD.md).
- **In-editor dashboard** — an optional local VS Code panel surfaces budget, security posture, and governance proposals at a glance, over the same MCP server. No external services, no daemon, no marketplace install required. See [vscode-extension/](vscode-extension/).

## Architecture — one source, three emitters

```
PromptWise core  (router · roles · compliance · context engine · workflow_planner)
        ├─▶ MCP tools      → route_request, plan_workflow, owasp_scan …  (90)
        ├─▶ SKILL.md packs → 81 portable packs in skill_packs/
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
| `skill_packs/` | 81 portable `SKILL.md` role/technique packs (incl. `agile/` personas; copy into any agent) |
| `hooks/` | Claude Code lifecycle hooks — runtime security/policy/audit enforcement (fail-open) |
| `commands/`, `agents/` | Plugin slash commands and sub-agents |
| `.claude-plugin/` | Plugin + marketplace manifests, the `/promptwise` hub skill |
| `config/` | Pricing, providers, roles, security, compliance config |
| `AGENTS.md` | Universal project-context emitter |
| `docs/` | Integration guides (configuration reference, multi-platform setup) |
| `vscode-extension/` | Optional local VS Code panel — Budget/Security/Governance dashboard, TypeScript, builds to a local `.vsix`, zero external services |

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

## VS Code panel (optional)

A local Budget/Security/Governance dashboard, in-editor. Spawns the same MCP
server over stdio (via the official `@modelcontextprotocol/sdk`) — no
external services, no daemon, no network calls, no marketplace publish.

```bash
cd vscode-extension
npm install
npm run package
code --install-extension promptwise-panel-0.1.0.vsix
```

Run **PromptWise: Open Panel**. See
[vscode-extension/README.md](vscode-extension/README.md) for settings and
development notes.

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

VS Code panel (optional, separate package):

```bash
cd vscode-extension && npm install && node --test test/*.test.ts
```

## Status

**Early-stage, building in public.** v1.3 ships the engine, eight native IDE/CLI
config emitters (Claude, Codex/AGENTS.md, Cursor, Copilot, Cline, Gemini, Windsurf,
JetBrains AI Assistant) plus a single-file web-agent bundle for ChatGPT/Gemini/
Claude.ai web chat, the 81
skill packs (incl. the `agile/` method personas), the self-contained workflow planner, the
governed agile method (quality gates, policy-as-code, hash-chained audit trail), the runtime
enforcement hooks layer, a continuous learning loop with offline skill auto-optimization,
an autonomous governor (policy-gated, reversible, advise-by-default) with a budget-guardian
overlay, a durable eval + red-team regression harness (offline, baseline-diffed, pass/fail
gated), MCP supply-chain auditing, a searchable trace, diagram generators, and a
task/effort/usage tracker. New in v1.3: a **reasoning-effort axis** (low/medium/high,
independent of model tier, with its own outcome-learning adapter mirroring the model-tier
router), a **response-size cap** at the `call_tool` choke point so no tool response is
ever unbounded, and **cost + audit logging for skill invocations** (`invoke_skill`/
`skill_chain` results were computed but never persisted before — now every successful
execution shows up in cost reports and the audit trail). The 90 MCP tools are registered
through a decorator-based tool registry (one source of truth per tool — no hand-synced
definition/handler pair to drift, now organized into a `handlers/` package of 20 category
files instead of one monolithic `server.py`), and an optional local VS Code panel
(`vscode-extension/`) surfaces budget, security, and governance at a glance over the same
MCP server, zero external services. Everything runs directly from PromptWise — local-first,
no third-party integrations, air-gapped by default.

New in v1.4: a **compliance report card** (OWASP LLM Top 10 2025 / NIST AI RMF / MITRE
ATLAS), an **OpenTelemetry GenAI exporter** (stdlib-only, no new dependency), **policy
inheritance** (`extends:` org → team → project, tighten-only), **SIEM-streamable audit
sinks** (webhook/syslog), **within-tier cost-aware model routing** (prefers a cheaper
active model in the same quality tier under moderate budget pressure, before ever
collapsing to the cheapest tier), and **dashboard auth/RBAC** — the dashboard now binds
`127.0.0.1` by default (fixed an accidental LAN-exposure default) and a non-loopback bind
requires configured credentials, opt-in and zero-friction for solo use.

## License

MIT — see [LICENSE](LICENSE). Open standards are credited in [NOTICE](NOTICE).
