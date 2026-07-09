# PromptWise Cross-Host Portability

**Phase 7 §7.4 — platform-reach hardening**

PromptWise compiles ONE governance source (policy + skill packs + method) into
every agent's native rules file via the config emitter. This guide covers the
single check that keeps that surface consistent across every supported host, and
the host-neutral CI snippet that runs the governance gates in any pipeline.

---

## Supported hosts

The portability check covers exactly the hosts PromptWise can emit a config for
(from `config_emitter.TARGETS`):

| Host key | Native rules file |
|----------|-------------------|
| `claude` | `CLAUDE.md` |
| `agents` | `AGENTS.md` (also read by Codex) |
| `cursor` | `.cursor/rules/promptwise.mdc` |
| `copilot` | `.github/copilot-instructions.md` |
| `cline` | `.clinerules` |
| `gemini` | `GEMINI.md` |
| `windsurf` | `.windsurfrules` |

These are config-file conventions, not model ids. Routing stays host-neutral —
tiers/families only (`fast` / `balanced` / `powerful`).

---

## The portability check

`core/portability_check.py` validates that, for each supported host, the emitted
config is:

1. **present** — the native rules file exists in the repo;
2. **well-formed** — it carries the PromptWise managed block markers;
3. **in sync** — re-rendering the current skill/agent surface would not change it.

"In sync" is derived by reusing the emitter's own drift detection
(`ConfigEmitter.sync(mode="check")`), so there is no duplicated emit logic. The
surface — `skill_packs/` families, `agents/*.md`, and `commands/*.md` — is folded
into a fingerprint carried in the governance bundle, so adding or removing any
pack, agent, or command makes every host config read as **stale** until it is
re-emitted with `sync_agent_config`.

Drift is reported precisely, naming the host and the problem:

```
PromptWise portability — overall: DRIFT
  [ok]    claude (CLAUDE.md): present, well-formed, in sync
  [drift] gemini (GEMINI.md): missing emitted config
drift:
  - gemini: missing GEMINI.md — run sync_agent_config to emit it
```

### Run it

Via the MCP tool:

```jsonc
// tool: check_portability
{ "repo_root": ".", "emit_ci": false }
// -> { "ok": bool, "drift": [...], "hosts": [ { host, path, present, in_sync, well_formed, issues } ] }
```

Or via the slash command: `/promptwise:portability`.

---

## Host-neutral CI snippet

`emit_ci_snippet()` (also available via `check_portability` with `emit_ci: true`)
returns a generic pipeline snippet that runs the governance gates in any runner.
It references tiers/families only — no branded model ids and no CI-vendor lock-in
beyond a generic `stages`/`steps` example:

```yaml
# PromptWise governance gate — host-neutral CI snippet (Phase 7 §7.4).
stages:
  - governance

promptwise-governance-gate:
  stage: governance
  steps:
    - name: security-suite
      run: python -m promptwise gate security --fail-on high
    - name: quality-gate
      run: python -m promptwise gate quality --min PASS
    - name: cross-host-portability
      run: python -m promptwise gate portability
  routing:
    default_tier: balanced       # fast | balanced | powerful
    escalate_to: powerful        # high-stakes / regulated changes
    families: [local, hosted]    # keep host-neutral; no vendor lock-in
```

Adapt the `stages`/`steps` shape to your runner of choice — the gate logic and
routing policy are identical everywhere PromptWise runs.
