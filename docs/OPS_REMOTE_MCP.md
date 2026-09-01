# PromptWise Remote MCP Transport — Ops Guide

Companion to docs/superpowers/specs/2026-09-01-remote-mcp-transport-design.md
and docs/superpowers/plans/2026-09-01-remote-mcp-transport.md.

## What this is

An optional HTTP transport (Streamable HTTP, the current MCP spec's
recommended network transport) alongside the default stdio transport.
Off by default -- existing local users are unaffected. Serves two use
cases: your own multiple devices, and a team pointing multiple clients
at one instance you host. Third-party MCP connector apps (ChatGPT
Desktop-style, mobile apps built by someone else) are NOT supported yet
-- that needs OAuth 2.1 / dynamic client registration, a separate,
larger, deliberately deferred increment.

## Enabling it

1. Generate a raw token per person/device who needs access:

       python -c "import secrets; print(secrets.token_hex(32))"

2. Hash it and add to `config/mcp_auth.yaml` (copy from
   `config/mcp_auth.yaml.example` first):

       python -c "from promptwise.dashboard.auth import hash_credential; print(hash_credential('<raw token from step 1>'))"

3. Distribute the RAW token to that person/device out-of-band (chat,
   password manager, etc.) -- never commit it, never put it in the
   yaml file (only the hash goes there).

4. Start the server with the HTTP transport:

       PROMPTWISE_TRANSPORT=http promptwise-server

   Optional env vars: `PROMPTWISE_HTTP_HOST` (default `127.0.0.1` --
   set to `0.0.0.0` or a specific interface to actually accept remote
   connections), `PROMPTWISE_HTTP_PORT` (default `8766`),
   `PROMPTWISE_MCP_CREDENTIALS_PATH` (default `config/mcp_auth.yaml`).

5. Point your remote MCP client at `http://<host>:<port>/mcp` with
   `Authorization: Bearer <raw token>`.

## Per-call tool RBAC

Once the remote transport is enabled (above), every remote tool call is
also gated by role: `viewer` tokens (see `config/mcp_auth.yaml`'s
`role:` field) can only call the ~37 read-only tools listed as `viewer`
in `config/mcp_tool_roles.yaml` (reports, lookups, queries, checks);
everything else requires `admin`. This does NOT apply to local/stdio
usage -- your own Claude Code session via stdio is completely
unaffected, same as before.

To grant a specific token viewer-eligible access to a tool not
currently listed as `viewer`, edit `config/mcp_tool_roles.yaml` and add
`<tool_name>: viewer` under `tool_roles:` -- takes effect on the very
next remote call, no restart needed (the file is read fresh per call,
same as `config/mcp_auth.yaml`'s credential reloading).

A denied call returns a `PermissionDenied` JSON error and is recorded
to the audit trail (`gate_decision: FAIL`) -- check `query_audit` (as
an admin token) if you need to see denial history. Note that the MCP SDK
validates a tool call's arguments against its schema BEFORE PromptWise's
own RBAC check runs, so a denied caller sending malformed arguments to an
admin-only tool may see a schema-validation error (revealing the tool's
expected argument shape) rather than the `PermissionDenied` message -- this
is a property of the underlying transport layer, not a bypass (the call is
still fully denied either way), but worth knowing if you're auditing what an
unauthorized caller can observe.

## What this does NOT do

- No OAuth / dynamic client registration -- a third-party app that
  expects to do an OAuth handshake will not work against this
  transport.
- No multi-tenant data isolation -- every connected client shares the
  same PromptWise instance's data (same as today's dashboard).
- No TLS termination -- put this behind a reverse proxy (nginx, Caddy,
  a cloud load balancer) for anything beyond `127.0.0.1`/a trusted LAN.
  **WARNING:** Setting `PROMPTWISE_HTTP_HOST` to `0.0.0.0` or any
  non-loopback address sends Bearer tokens over plaintext HTTP with no
  built-in warning from the code. The operator is responsible for
  putting TLS in front of this (reverse proxy) before binding beyond
  `127.0.0.1` or a fully trusted LAN.
- No rate limiting / connection quotas -- an ops concern for whoever
  deploys this, not built into PromptWise itself.

## Manual verification checklist (not run in CI -- no real remote-network environment there)

- [ ] Start with `PROMPTWISE_TRANSPORT=http`; confirm the process stays
      up and does not silently fall back to stdio.
- [ ] Connect a real MCP client (or `curl -X POST http://127.0.0.1:8766/mcp -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'`)
      with a valid token; confirm a non-401 response.
- [ ] Same request with no `Authorization` header; confirm 401.
- [ ] Same request with a wrong token; confirm 401.
- [ ] Open two connections with two different valid tokens; run a tool
      call on each; confirm `session_cost_report` shows them as two
      distinct `session_id`s, not merged into one.
- [ ] Kill the process while a connection is open; confirm it exits
      cleanly (no hung port).
