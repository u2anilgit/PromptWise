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

4. Set the `PROMPTWISE_DB_URL` environment variable on every team
   member's machine to the full connection string, credentials included:

       export PROMPTWISE_DB_URL="postgresql+asyncpg://promptwise_team:<password>@<host>:5432/promptwise"

   Put this in your shell profile, a `.env` file loaded by your process
   manager, or your secrets manager -- any mechanism that keeps it out of
   a tracked file. **`config/promptwise.yaml` IS tracked in git** (only
   `config/policy.yaml` and `config/admin.yaml` are gitignored in this
   repo) -- never put a real password in `identity.db_url` there. When
   set, `PROMPTWISE_DB_URL` always takes precedence over whatever
   `identity.db_url` the yaml has.

   `identity.db_url` in `config/promptwise.yaml` still exists as a
   non-secret fallback/default -- use it only for local dev pointed at a
   local Postgres with no real credentials (e.g.
   `postgresql+asyncpg://localhost/promptwise_dev`), never for a real
   team connection string.
5. Distribute the password out-of-band (same discipline as
   `config/dashboard_auth.yaml`'s credential hashing doc).
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
- [ ] Set `PROMPTWISE_DB_URL` to the real Postgres connection string;
      confirm it takes precedence over any `identity.db_url` configured
      in `config/promptwise.yaml`.

## Dashboard auth is credential-only in Phase 1

The dashboard's `require_role` gate authenticates only a Bearer
credential from `config/dashboard_auth.yaml` (see that file's
`.example` companion) -- there is no AD-group-based dashboard auth in
Phase 1. An earlier draft of this feature resolved a role from the AD
groups of the OS user running the dashboard *process* rather than the
actual HTTP requester; the Phase 1 final review found that unsafe on a
non-loopback bind (it would grant a network requester with no
credential at all whatever role the server operator's own account
mapped to) and it was removed. Directory-backed dashboard auth needs
per-request SSO (e.g. Kerberos/SPNEGO) to be done safely -- deferred to
Phase 2. `resolve_role_from_groups`/`load_ad_group_map` remain in
`dashboard/auth.py`, unwired, for that future work.

## Deferred (per spec's open questions, resolved here)

- `get_identity()` as a standalone read-only MCP tool: **not added in
  Phase 1** -- `ctx.identity` is internal-only (audit/cost/dashboard
  wiring). Revisit if a skill/agent has a concrete need to read it
  directly.
