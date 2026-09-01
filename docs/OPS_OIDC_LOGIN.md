# PromptWise OIDC Dashboard Login — Ops Guide

Companion to docs/superpowers/specs/2026-09-01-oidc-dashboard-login-design.md
and docs/superpowers/plans/2026-09-01-oidc-dashboard-login.md.

## What this is

Optional OIDC (OpenID Connect) login for the dashboard, supplementing --
never replacing -- the existing static-credential Bearer-token path
(config/dashboard_auth.yaml). Off by default. SAML is not supported;
build only against an OIDC-compliant IdP (Okta, Entra ID/Azure AD,
Google Workspace, Auth0, Keycloak, and most modern IdPs all speak OIDC).

## Enabling it

1. Register PromptWise as an OIDC application in your IdP. You'll need:
   - The IdP's issuer URL (e.g. `https://your-org.okta.com`,
     `https://login.microsoftonline.com/<tenant-id>/v2.0`)
   - A client ID and client secret the IdP issues you
   - Register the redirect URI as `http://<your-host>:<port>/auth/callback`
     (or `https://...` if you've put TLS in front, which you should for
     anything beyond `127.0.0.1`)

2. Generate a random session-cookie signing key:

       python -c "import secrets; print(secrets.token_hex(32))"

3. Set these environment variables before starting the dashboard:

       PROMPTWISE_OIDC_ISSUER=https://your-org.okta.com
       PROMPTWISE_OIDC_CLIENT_ID=<from your IdP>
       PROMPTWISE_OIDC_CLIENT_SECRET=<from your IdP -- never commit this>
       PROMPTWISE_OIDC_REDIRECT_URI=http://<your-host>:<port>/auth/callback
       PROMPTWISE_DASHBOARD_SECRET_KEY=<the random key from step 2>

   Optional: `PROMPTWISE_OIDC_GROUP_CLAIM` (default `groups`) if your IdP
   emits role/group info under a different ID-token claim name (e.g.
   `roles`).

4. Copy `config/oidc_roles.yaml.example` to `config/oidc_roles.yaml` and
   map your IdP's group names to `admin`/`viewer` roles. Non-secret --
   only claim names and role names, safe to keep in a tracked file
   (unlike the client secret above, which stays an environment variable
   only).

5. Start the dashboard as usual (`promptwise serve`). Note: even if using
   OIDC as your only login method, `config/dashboard_auth.yaml` must
   exist (even with zero entries: `entries: []`) before allowing a
   non-loopback bind; this is a known configuration requirement and not
   a bug. A "Login with SSO" option is now available -- click through
   `/auth/login` to start the flow.

## What this does NOT do

- No SAML support.
- No SCIM/automated user provisioning -- group membership in your IdP is
  read at login time only; a user removed from a group mid-session keeps
  their role until their session expires or they re-login.
- No IdP-side Single Logout -- `/auth/logout` clears the local session
  only, it does not call back to the IdP to end the IdP-side session too.
- Does not touch the remote MCP transport's token auth
  (config/mcp_auth.yaml, docs/OPS_REMOTE_MCP.md) -- that stays exactly
  as it was.
- **No access-list gate on WHO logs in:** any user who successfully
  authenticates via the IdP receives at least `viewer` dashboard access
  by default. There is no group-membership check that denies login
  entirely; role assignment is based on IdP group mappings (unmapped
  groups default to `viewer`, not rejection). If you need to restrict
  WHO can access the dashboard at all (not just which role they receive),
  that access control must be enforced at the IdP side (e.g., only
  grant the PromptWise application access to specific IdP groups),
  not in PromptWise's configuration.
- **Plain HTTP over non-loopback hosts carries plaintext cookies:**
  binding the dashboard to a non-loopback address without TLS means
  OIDC session cookies -- which grant admin access for users with
  admin-mapped groups -- travel unencrypted. PromptWise sets
  `SESSION_COOKIE_SECURE` based on whether your `PROMPTWISE_OIDC_REDIRECT_URI`
  uses `https://`, but that flag only protects the cookie in transit if
  you have actually deployed TLS in front of the dashboard. For anything
  beyond `127.0.0.1` or a fully trusted LAN, place PromptWise behind a
  reverse proxy (nginx, Caddy, a cloud load balancer) that terminates
  TLS. See docs/OPS_REMOTE_MCP.md's reverse-proxy guidance for the same
  underlying pattern -- the same TLS-terminating reverse proxy can serve
  both the dashboard and the remote MCP transport.

## Manual verification checklist (not run in CI -- no real IdP environment there)

- [ ] Register a real test application in a real IdP (Okta/Entra ID free
      tier, or similar) with the redirect URI above.
- [ ] Set all required env vars; start the dashboard; confirm it does
      NOT refuse to start (i.e. the secret-key check passes).
- [ ] Temporarily unset `PROMPTWISE_DASHBOARD_SECRET_KEY` with OIDC
      otherwise configured; confirm the dashboard refuses to start with a
      clear error, not a silent insecure fallback.
- [ ] Click `/auth/login`; confirm a real redirect to your IdP's login
      page.
- [ ] Log in at the IdP; confirm redirect back to `/auth/callback` then
      to `/`, and that `/api/*` routes now succeed with no Authorization
      header (session cookie carries the identity).
- [ ] Confirm your IdP-side group membership maps to the expected role
      (an admin-mapped group grants admin-only routes; a viewer-mapped or
      unmapped group does not).
- [ ] Click `/auth/logout`; confirm `/api/*` now returns 401 again until
      you log in again.
- [ ] Confirm a Bearer-token request (existing static-credential path)
      still works unmodified, alongside OIDC being enabled.
