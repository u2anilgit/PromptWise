# Contributing to PromptWise

Early-stage and built in public — contributions, issues, and ideas welcome.

## Dev setup

```bash
git clone https://github.com/u2anilgit/PromptWise.git
cd PromptWise
pip install -e ".[dev]"
pytest            # if/when tests are present
```

The MCP server runs with `python -m promptwise.server` (needs `PYTHONPATH=src`, or
`pip install -e .`).

## Project layout

- `src/promptwise/` — engine. New MCP tools: add a `Tool(...)` to `_TOOL_DEFS`, an
  `elif name == "..."` branch in `call_tool`, and (if stateful) a field on
  `ServerContext`. Keep core logic in `core/` modules that return small dataclasses.
- `skill_packs/` — portable `SKILL.md` packs. Frontmatter must include `name`,
  `description`, `triggers`; optionally `roles`, `model_tier`, `output_schema`.
- `config/` — YAML config; hot-reloadable via `reload_config`.

## Conventions

- Python ≥ 3.10, type hints, small focused modules.
- A new skill pack is a single `SKILL.md` with frontmatter + a prompt body — no code.
- Keep changes portable: don't hard-code one agent's paths; emit MCP / SKILL.md / AGENTS.md.

## What NOT to commit

Implementation plans, specs, IDE/agent caches, memory files, and context dumps are
git-ignored on purpose (see `.gitignore`). The repo ships the plugin codebase + docs only.
