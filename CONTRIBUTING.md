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

- `src/promptwise/` — engine. New MCP tools: add an `async def _handle_<name>(ctx, arguments)`
  decorated with `@tool(name=..., description=..., schema={...})` in `server.py`, and
  (if stateful) a field on `ServerContext`. The decorator auto-registers the tool into
  `_TOOL_DEFS`/`_HANDLERS` and `call_tool` dispatches it automatically — no separate
  list or dict edit needed. Keep core logic in `core/` modules that return small
  dataclasses.
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
