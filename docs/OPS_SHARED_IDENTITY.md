# PromptWise Enterprise Identity — Phase 1 Ops Guide

Companion to docs/superpowers/specs/2026-08-31-promptwise-enterprise-identity-phase1-design.md
and docs/superpowers/plans/2026-09-01-enterprise-identity-phase1.md.

## LDAP library

`ldap3` (pure-Python, no C extension / system libldap dependency), pinned
`>=2.9,<3.0` in the optional `ldap` extras group:

    pip install "promptwise[ldap]"

Not installed by default. When absent, `core/identity.py` fails open to
the env-var tier -- no error, no degraded functionality beyond losing
group data.

## Enabling Tier 1 (real LDAP bind)

1. Install the extras group above on the machine running the MCP server.
2. Set `identity.ldap_server` and `identity.ldap_search_base` in
   `config/promptwise.yaml` (see the `identity:` section added there).
3. The bind uses SASL/GSSAPI against the current Kerberos ticket -- no
   password is stored or handled by PromptWise. This only works on a
   domain-joined machine with a valid ticket (e.g. after Windows login,
   or `kinit` on Linux/macOS joined to the domain).
4. If the bind fails for any reason (unreachable DC, no ticket, wrong
   search base), identity silently falls back to Tier 2 (env vars) --
   check `resolve_identity(...).source` if you need to confirm which
   tier actually resolved.

## Shared team Postgres

1. Stand up a Postgres instance the whole team can reach (out of scope
   for PromptWise itself -- use your existing infra, e.g. a managed
   Postgres instance, a Docker container on a shared host, etc.).
2. Create a database and a role with `CREATE`/read-write privileges,
   e.g.:

       CREATE DATABASE promptwise;
       CREATE USER promptwise_team WITH PASSWORD '<generate one>';
       GRANT ALL PRIVILEGES ON DATABASE promptwise TO promptwise_team;

3. Install the async Postgres driver on every machine that will connect
   (not bundled by default -- add it alongside your other dependencies):

       pip install asyncpg

4. Set `identity.db_url` in `config/promptwise.yaml` on every team
   member's machine:

       identity:
         db_url: "postgresql+asyncpg://promptwise_team:<password>@<host>:5432/promptwise"

5. Distribute the password out-of-band (same discipline as
   `config/dashboard_auth.yaml`'s credential hashing doc) -- never commit
   `config/promptwise.yaml` with a real password in it; keep the real
   file gitignored per this repo's existing convention
   (see config/*.yaml vs config/*.example.yaml).
6. `get_admin_settings()` surfaces `db_health` (reachable/warning) once
   `identity.db_url` is a `postgresql` URL -- check it if team members
   report stale-looking dashboard data.
7. `handlers/detection.py`, `core/behavior_baseline.py`, and
   `handlers/fleet.py` still open their own local-sqlite `MemoryManager`
   for baseline/anomaly-detection state -- that state intentionally stays
   per-machine in Phase 1 (only the cost/ROI/session/audit-adjacent path
   through `server.py`/`cli.py` is Postgres-aware). Revisit if per-machine
   baseline state becomes a real pain point.

## Manual verification checklist (not run in CI -- no real AD/Postgres environment there)

Run this on an actual domain-joined machine with access to a real
Postgres instance before calling Phase 1 "verified in production":

- [ ] `pip install "promptwise[ldap]" asyncpg` on the test machine.
- [ ] Set `identity.ldap_server`/`identity.ldap_search_base` to the real
      domain controller; confirm `resolve_identity(config.identity).source == "ldap"`
      and `.groups` contains the expected AD group names (not full DNs).
- [ ] Temporarily point `identity.ldap_server` at an unreachable host;
      confirm resolution falls back to `"env"` within a few seconds (no
      hang, no exception surfaced to the tool call).
- [ ] Run a governed tool that records to audit (e.g. `check_policy` with
      `record_to_audit=true`, no explicit `actor`); confirm the resulting
      audit record's `actor` is the real AD username.
- [ ] Run `track_roi`; confirm `roi_stats.developer`/`.role` reflect the
      real AD username/groups, not "Anonymous"/"Dev".
- [ ] Set `identity.db_url` to the real Postgres instance; start the MCP
      server and dashboard on two different machines pointed at the same
      URL; confirm both see the same cost/ROI history.
- [ ] Temporarily point `identity.db_url` at an unreachable Postgres
      host; confirm the dashboard/tools still function (fallback path)
      and `get_admin_settings().db_health.warning` is populated.
- [ ] Add an `ad_groups` mapping to `config/dashboard_auth.yaml` on a
      domain-joined dashboard host; confirm a browser with no
      `Authorization` header still gets the mapped role when the OS user
      running the dashboard process belongs to a mapped AD group, and is
      still rejected when it doesn't.

## Deferred (per spec's open questions, resolved here)

- `get_identity()` as a standalone read-only MCP tool: **not added in
  Phase 1** -- `ctx.identity` is internal-only (audit/cost/dashboard
  wiring). Revisit if a skill/agent has a concrete need to read it
  directly.
