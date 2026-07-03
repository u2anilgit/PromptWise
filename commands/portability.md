---
description: Check that the governance configs stay consistent across every supported host, and emit a host-neutral CI snippet, via PromptWise.
argument-hint: [repo path]
---

Use the PromptWise `check_portability` tool on the repo below to verify the emitted governance configs for every supported host (CLAUDE.md, AGENTS.md, .cursor/rules, copilot-instructions, .clinerules, GEMINI.md) are present, well-formed, and in sync with the current skill/agent surface (skill_packs / agents / commands). Report the overall PASS/DRIFT result and, for any drift, name the host and whether its config is missing or stale — then suggest running `sync_agent_config` to re-emit. Pass `emit_ci: true` when the user wants the host-neutral CI-snippet that runs the governance gates (security suite, quality gate, portability) using tiers/families only.

$ARGUMENTS
