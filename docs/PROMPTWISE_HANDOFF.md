# PromptWise Handoff

Date: 2026-09-04

## Release status

PromptWise is ready for the next project phase. PR #23 was merged into `main` after the security and reliability fixes were validated.

## Verified

- All 142 MCP tools were enumerated and dispatched through the tool boundary.
- Python test suite: 1547 tests passed.
- CI passed on Python 3.10, 3.11, and 3.12.
- CodeQL JavaScript/TypeScript, Python, Actions, and aggregate checks passed.
- Codex provider-aware model routing was verified for simple, balanced, and complex tasks.
- Extension tests passed: 24 passed and 2 environment-dependent tests skipped.
- Extension compilation succeeded.
- `npm audit`: 0 vulnerabilities.
- GitHub Dependabot open alerts after merge: 0.

## Completed improvements

- Remediated extension dependency vulnerabilities.
- Added safe Ruff resolution and CI development dependency support.
- Added configurable learning database path via `PROMPTWISE_LEARNING_DB_PATH`.
- Added Codex model families and provider-aware routing.
- Added all-tools smoke coverage and model resolver tests.
- Added testing and configuration documentation.
- Preserved a local backup at `.promptwise-safe-backup`.

## Optional follow-ups

These are not release blockers:

1. Update the GitHub AI code-scanning workflow, which currently requests the unsupported `gpt-5.3-codex` model.
2. Add a release tag/version and changelog entry for the merged fixes.
3. Run one clean-install verification from the merged `main` branch.
4. Enforce `npm audit` and the 142-tool smoke test in CI.
5. Periodically refresh provider pricing and model mappings.

## Workspace safety note

Unrelated local modifications and untracked agent configuration files were intentionally preserved and not included in the merge. Keep `.promptwise-safe-backup` until those changes are reviewed.

## Next phase

The next workstream is the Agentic OS project. PromptWise should be treated as the cross-agent intelligence layer providing MCP tools, portable skill packs, routing, context and memory optimization, cost control, security, compliance, governance, and workflow planning.
