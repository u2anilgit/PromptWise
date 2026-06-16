# PromptWise

**The cross-agent intelligence layer for AI coding agents.** Role-aware prompting, model
routing, cost & budget control, security/compliance scanning, framework orchestration,
and 55 portable skill packs — emitted in the formats every agent already reads.

> Built on open standards, not against them. PromptWise is a *conductor*, not a replacement
> for Cursor / Copilot / Claude Code.

**Works with:** Claude Code · Codex · Cursor · Gemini CLI · Copilot · any MCP host
**Standards:** MCP · SKILL.md · AGENTS.md

---

## Why

The ecosystem standardized. MCP (Linux Foundation–governed), SKILL.md, and AGENTS.md are
now the shared substrate across every major coding agent. PromptWise doesn't fight that —
it compiles its intelligence **down to those three formats** and adds the layer none of
them have:

- **Model routing** — right tier (Haiku/Sonnet/Opus) per task, with budget awareness.
- **Context-budget engineering** — compression, caching, batching, thread handoff.
- **Role intelligence** — 55 role/technique skill packs (banking, HIPAA, QA, TDD, ADR, …).
- **Compliance gating** — auditable PRD→architecture→story→commit chain for regulated teams.
- **Framework orchestration** — classify a task → recommend BMAD / Spec Kit / OpenSpec / TaskMaster instead of forcing you to pick among nine of them.

## Architecture — one source, three emitters

```
PromptWise core  (router · roles · compliance · context engine · framework_router)
        ├─▶ MCP tools      → route_request, recommend_framework, owasp_scan …  (60+)
        ├─▶ SKILL.md packs → 55 portable packs in skill_packs/
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
    "promptwise-v3": {
      "command": "python",
      "args": ["-m", "promptwise_v3.server"],
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
| `src/promptwise_v3/` | Engine: MCP server + core logic, security, plugins, transports |
| `skill_packs/` | 55 portable `SKILL.md` role/technique packs (copy into any agent) |
| `.claude-plugin/` | Plugin + marketplace manifests, the `/promptwise` hub skill |
| `config/` | Pricing, providers, roles, security, compliance config |
| `AGENTS.md` | Universal project-context emitter |
| `docs/` | Architecture plan (also published via GitHub Pages) + integration guides |

## Framework router

`recommend_framework` classifies a task by intent · scale · risk and routes it:

| Task shape | → Framework |
|------------|-------------|
| Greenfield + regulated | Spec Kit (+ constitution = compliance gate) |
| Full multi-role product build | BMAD-METHOD |
| Brownfield, gated change | OpenSpec |
| PRD → tasks only | TaskMaster |
| Save/event-triggered automation | Kiro-style hooks |

## Status

**Early-stage, building in public.** v1.0 ships the engine, the three emitters, the 55
skill packs, and the framework *recommender*. Live subprocess wrapping of BMAD/Spec Kit
and runtime constitution gating are on the roadmap (see `docs/`).

## License

MIT — see [LICENSE](LICENSE). Wrapped/recommended OSS is credited in [NOTICE](NOTICE).
