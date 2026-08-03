# PromptWise Development Configuration

## Security Hook Behavior (2026-08-01+)

The PromptWise security plugin runs a PreToolUse:Write/Edit hook (`pretooluse_secret_scan.py` -> `core/hook_bridge.py::pretooluse_scan`) that scans writes for secrets/destructive-command/injection patterns. It no longer hard-blocks (no more exit-2 hook error): a flagged write now returns `ask`, handing off to Claude Code's normal allow/deny permission prompt, and every finding is logged silently to `.promptwise/security_findings.jsonl` regardless of outcome.

**Standing exceptions (skip the prompt entirely) via the JIT permission system:**
```
grant_jit_permission(signature="SecurityScan:file:<path>")      # exempt one file
grant_jit_permission(signature="SecurityScan:project:<name>")   # exempt the whole project
```
Grants are time-boxed (default 60min, max 480min/8h) and auto-revert to the normal prompt on expiry. `list_jit_permissions()` / `revoke_jit_permission(signature=...)` manage them.

Note: `.claude/settings.json` `permissions.allow` patterns (e.g. `Write(src/*)`) control Claude Code's own permission engine, not this hook — the hook always runs regardless and is the thing that used to hard-block.

## Cross-agent preflight pipeline (2026-08-03+)

`userpromptsubmit_policy` now runs a combined pass (`core/preflight.py::run_preflight`) on every prompt: rewrite advisory, secret/injection scan, task-type classification (bugfix/docs/refactor/enhancement/new_code), model/tier routing, and an opt-in shortlist of the last 2-3 current models per tier. All advisory — an MCP server cannot force a host to swap its active model mid-turn, so this surfaces via `additionalContext` (the `warn` hook action), same channel as before. The model shortlist is off by default (`PROMPTWISE_MODEL_RETENTION=on` to enable); `doctor` flags when `config/models.yaml`'s newest `release_date` is >120 days old. Cross-provider suggestions are text-only, never dispatched. Design: `docs/superpowers/specs/2026-08-03-preflight-pipeline-design.md`.
