# PromptWise

**The governance & intelligence layer for AI agents.** Role-aware prompting, model
routing, cost & budget control, security/compliance scanning, responsible-AI advisories,
workflow planning, a governed agile method, runtime enforcement hooks, and 81 portable skill
packs — emitted in the formats every agent already reads.

> Built on open standards, not against them. PromptWise is a *conductor*, not a replacement
> for Cursor / Copilot / Claude Code.

**Works with:** Claude Code · Claude Desktop (tools only, no hooks) · Codex · Cursor ·
Gemini CLI · Copilot · Windsurf · JetBrains AI Assistant · Cline · Aider · Goose ·
OpenHands · Grok Build/Grok CLI (reads CLAUDE.md natively) · any MCP host
**Standards:** MCP · SKILL.md · AGENTS.md

[![CI](https://github.com/u2anilgit/PromptWise/actions/workflows/ci.yml/badge.svg)](https://github.com/u2anilgit/PromptWise/actions/workflows/ci.yml)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Skill packs](https://img.shields.io/badge/skill%20packs-81-7C5BD4.svg)
![MCP tools](https://img.shields.io/badge/MCP%20tools-107-4C5BD4.svg)

📖 **[User Guide](docs/USER_GUIDE.md)** · [Install](INSTALL.md) · [Configuration](CONFIGURATION.md) · [Architecture](docs/ARCHITECTURE.md) · [Landing page](https://u2anilgit.github.io/PromptWise/)

![PromptWise landing page walkthrough](docs/promptwise-landing-scroll.gif)

---

## Why

The ecosystem standardized. MCP (Linux Foundation–governed), SKILL.md, and AGENTS.md are
now the shared substrate across every major coding agent. PromptWise doesn't fight that —
it compiles its intelligence **down to those three formats** and adds the layer none of
them have:

- **Model routing** — right tier (Haiku/Sonnet/Opus) per task, with budget awareness.
- **Preflight pipeline** — every prompt, in every connected host, gets one combined
  pass before work starts: rewrite advisory, secret/injection scan, task-type
  classification (bugfix/docs/refactor/enhancement/new-code), model/tier routing,
  and an opt-in shortlist of the last 2-3 current models per tier. Advisory-only by
  design (an MCP server can't force a host to swap models mid-turn) — surfaces as
  session context, never blocks. See `core/preflight.py`.
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
- **Runtime enforcement** — Claude Code lifecycle hooks auto-run security/policy/audit checks on every Write/Edit and tool call. A flagged write defers to Claude Code's normal allow/deny prompt (never a hard, opaque block) and is logged silently either way; standing exceptions are time-boxed JIT grants (`grant_jit_permission`), scoped to one file or a whole project. Destructive shell commands and runaway tool-call loops still hard-deny. Fail-open throughout: a hook error never wedges the session. See `hooks/`.
- **Red-team regression harness** — a durable, offline attack/benign corpus run against the security scanner, diffed against a stored baseline to catch both missed detections and false-positive regressions (`run_red_team_harness`). All scanning is air-gapped by default — no unconditional network calls.
- **Continuous learning** — corrections become durable, searchable rules (FTS5) replayed before relevant work; packs self-optimize offline. Local-first, air-gapped safe.
- **Workflow planning** — classify a task → an ordered chain of PromptWise's *own* skill packs (PRD → design → stories → TDD → review). Fully self-contained, no external tools.
- **Governed agile method** — analyst→pm→architect→po planning then per-story sm→dev→qa loop, with context-engineered stories, advisory quality gates, policy-as-code, and a hash-chained audit trail. See [docs/AGILE_METHOD.md](docs/AGILE_METHOD.md).
- **In-editor dashboard** — an optional local VS Code panel surfaces budget, security posture, and governance proposals at a glance, over the same MCP server. No external services, no daemon, no marketplace install required. See [vscode-extension/](vscode-extension/).

## Architecture — one source, three emitters

```
PromptWise core  (router · roles · compliance · context engine · workflow_planner)
        ├─▶ MCP tools      → route_request, plan_workflow, owasp_scan …  (107)
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

**Early-stage, building in public.** Package version `1.10.0` in `pyproject.toml`
(the changelog trails a few shipped features — see `docs/ROADMAP.md` for the live,
accurate ledger); 107 MCP tools, 81 portable skill packs, ~1050 tests, registered
through a decorator-based tool registry (one source of truth per tool, organized into a
`handlers/` package of 20 category files instead of one monolithic `server.py`).
Everything runs directly from PromptWise — local-first, no third-party integrations,
air-gapped by default.

**Core engine:** model-tier routing with budget awareness, a reasoning-effort axis
(low/medium/high, independent of tier, with its own outcome-learning adapter), a
response-size cap at the `call_tool` choke point so no tool response is ever unbounded,
context-budget engineering (compression/caching/batching/handoff), and cost + audit
logging for every skill invocation.

**Cross-agent portability — one governance source, 11 native emitters:** Claude,
Codex/AGENTS.md, Cursor, Copilot, Cline, Gemini, Windsurf, JetBrains AI Assistant,
Aider (`CONVENTIONS.md`), Goose (`.goosehints`), OpenHands
(`.openhands/microagents/repo.md`) — plus Grok Build/Grok CLI, which needs no emitter
of its own since it natively auto-reads CLAUDE.md/AGENTS.md. `detect_agents()` probes
all of them (bar Grok, which has no marker file to detect) so `propose_agent_config`'s
auto-target-selection actually sees every host you've configured. Also: a single-file
web-agent bundle (`export_web_bundle`) for ChatGPT/Gemini/Claude.ai web chat, where
there's no IDE/CLI/MCP surface to emit into.

**Zero-manual-step onboarding:** `python -m promptwise bootstrap --sync-agents` detects
every host present in a repo and writes their native config in one command — the
skill-pack surface (active pack families + drift fingerprint) is included automatically,
and Codex additionally gets its MCP server registered directly in a repo-scoped
`.codex/config.toml`, no separate manual step required.

**Governance & security:** the runtime enforcement hooks layer (`hooks/`) — a flagged
Write/Edit defers to Claude Code's normal allow/deny prompt instead of a hard block,
logs silently either way, and standing exceptions are time-boxed JIT grants scoped to
a file or a whole project; destructive shell commands and runaway tool-call loops still
hard-deny. A compliance report card (OWASP LLM Top 10 2025 / NIST AI RMF / MITRE ATLAS),
an OpenTelemetry GenAI exporter, policy inheritance (`extends:` org → team → project,
tighten-only), SIEM-streamable audit sinks, within-tier cost-aware model routing, and
dashboard auth/RBAC (binds `127.0.0.1` by default; non-loopback requires credentials).
An append-only, human-reviewed injection-detection corpus refresh workflow
(`review_corpus_candidates`/`promote_corpus_candidates`, before/after precision-recall
diffed on every promotion) keeps the prompt-injection detector's benchmark corpus
current without turning it into a live, unaudited ML classifier. A durable eval +
red-team regression harness (offline, baseline-diffed, pass/fail gated), MCP
supply-chain auditing, a searchable trace, and prompt version rollback/replay round out
the governance surface.

**Method & learning:** the governed agile method (analyst→pm→architect→po planning,
per-story sm→dev→qa loop, quality gates, policy-as-code, hash-chained audit trail), the
self-contained workflow planner, a continuous learning loop with offline skill
auto-optimization, an autonomous governor (policy-gated, reversible, advise-by-default)
with a budget-guardian overlay, diagram generators, and a task/effort/usage tracker. An
optional local VS Code panel (`vscode-extension/`) surfaces budget, security, and
governance at a glance over the same MCP server, zero external services.

**Known gaps, sized but not built:** remote/mobile MCP access (server is stdio-only
today; ChatGPT-Desktop-style connectors and mobile apps need a hosted HTTP/SSE
transport, auth, and per-user state — a real architecture shift, not config) and
cost-conscious routing over deprecated/prior-gen models (the registry already retains
deprecated model pricing; the router just never reaches for it — a small, well-scoped
addition once the default-on-vs-opt-in question is settled).

## License

MIT — see [LICENSE](LICENSE). Open standards are credited in [NOTICE](NOTICE).
