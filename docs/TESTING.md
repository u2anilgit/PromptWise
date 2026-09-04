# PromptWise verification

The regression suite includes `tests/test_all_tools_smoke.py`, which dispatches
every registered MCP tool through the shared `call_tool` choke point using empty
business inputs and temporary state. Validation or missing-record responses are
allowed; unknown-tool responses and uncaught failures are not.

The model-routing contract is provider-aware. Complexity is classified into
intent and stakes, mapped to fast/balanced/powerful tiers, and resolved through
`config/models.yaml`. For Codex, simple summaries use `codex-5.5-base`, complex
production code uses `codex-5.5-max`, and budget-pressure fallbacks stay within
the Codex provider. Routing is advisory: MCP can recommend a model to the host,
but cannot force a coding agent to switch models mid-turn.

Learning storage can be relocated with `PROMPTWISE_LEARNING_DB_PATH` or
`identity.learning_db_path` in `config/promptwise.yaml`. The environment variable
takes precedence and is useful for managed or restricted workstations.

Before release, run:

```text
python -m pytest
```

Then build and install the wheel in a clean environment and repeat the tool-list,
tool-dispatch, and representative MCP transport checks.
