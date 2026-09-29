---
description: Grant, renew, revoke or list time-boxed JIT permissions (e.g. Bash:git) via PromptWise.
argument-hint: grant|renew|revoke|list [signature] [ttl_minutes]
---

Manage PromptWise JIT permission grants. Parse `$ARGUMENTS` as `<action> [signature] [ttl_minutes]`:

- `list` (or no arguments): call `list_jit_permissions` and show each signature with its status (active/expired) and expiry. If any are expired, offer to renew them.
- `grant <signature> [ttl_minutes]` / `renew <signature> [ttl_minutes]`: call `grant_jit_permission` (it upserts, so it re-enables an expired grant). Default ttl 60, max 480 minutes. Report the new expiry.
- `revoke <signature>`: call `revoke_jit_permission` and confirm the record is cleared.

Signature examples: `Bash:git`, `mcp__promptwise__run_governor`. Matching is coarse (first command token), so `Bash:git` covers every git invocation -- warn the user before granting a broad signature for a long TTL, and prefer short TTLs for commands where arguments matter.

$ARGUMENTS
