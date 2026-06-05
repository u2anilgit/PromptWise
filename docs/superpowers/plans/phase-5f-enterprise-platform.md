# PromptWise Phase 5F — Enterprise & Platform Integration

**Status:** Pending — start in fresh session after Phase 5A–5E complete  
**Source:** Gap analysis against Skills-promptwise.pdf (53 tools / 30 skills vision)  
**Pre-req:** All phases 5A–5E complete (36 skills, ~53 tools already)

---

## Goal

Bring tool count to 53+ matching the PDF product vision. Add real external integrations (Slack, Teams, GitHub Actions) and team/enterprise session management.

---

## Task F1 — Slack + Teams Alert Tools

**Files:**
- NEW `src/promptwise_v2/integrations/webhooks.py`
- `src/promptwise_v2/integrations/mcp_server_v2.py` (add 2 tools)

**Tools to add:**

| Tool | Inputs | Behaviour |
|------|--------|-----------|
| `send_slack_alert` | `webhook_url, message, level (info/warn/critical)` | POST to Slack webhook; include cost/threshold context; returns {ok, ts} |
| `send_teams_alert` | `webhook_url, message, level` | POST to Teams incoming webhook (Adaptive Card format); returns {ok} |

**webhooks.py:**
```python
class WebhookClient:
    async def send_slack(self, webhook_url: str, message: str, level: str) -> dict
    async def send_teams(self, webhook_url: str, message: str, level: str) -> dict
```

Use `httpx.AsyncClient` for HTTP calls. Timeout 10s. Return `{"ok": False, "error": str(e)}` on failure — never raise.

**Tests:** Mock httpx, test success + timeout + bad URL paths.

**Effort:** 1 day

---

## Task F2 — GitHub Actions Integration

**Files:**
- `src/promptwise_v2/integrations/github_actions.py` (NEW)
- `mcp_server_v2.py` (1 tool)
- `promptwise-action/action.yml` (NEW — GitHub Action definition)

**Tool:**

| Tool | Inputs | Behaviour |
|------|--------|-----------|
| `trigger_github_workflow` | `repo, workflow_id, ref, inputs?` | Calls GitHub API `POST /repos/{repo}/actions/workflows/{workflow_id}/dispatches`; needs `GITHUB_TOKEN` env var |

**action.yml** — GitHub Action that runs PromptWise security_check + code-review on PR diff:
```yaml
name: PromptWise Gate
on: [pull_request]
inputs:
  fail_on: {default: critical}
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v4
    - run: pip install promptwise-v2
    - run: promptwise-gate --fail-on ${{ inputs.fail_on }}
```

**github_actions.py:**
```python
class GitHubActionsClient:
    def trigger_workflow(self, repo, workflow_id, ref, inputs, token) -> dict
    def get_workflow_run_status(self, repo, run_id, token) -> dict
```

**Effort:** 1.5 days

---

## Task F3 — Team Session Management

**Files:**
- `src/promptwise_v2/core/team_session.py` (NEW)
- `mcp_server_v2.py` (4 tools)

**Tools to add:**

| Tool | Inputs | Behaviour |
|------|--------|-----------|
| `create_team_session` | `team_name, members[], role_budgets?` | Create shared session with per-role budget caps; returns session_id |
| `get_team_stats` | `team_session_id?, period?` | Aggregate usage across all members; return per-user + per-role breakdown |
| `set_role_budget` | `role, limit_usd, period` | Set per-role spending quota (e.g. Dev: $50/day, Architect: $100/day) |
| `export_team_report` | `team_session_id, format (json/csv)` | Full team usage report for billing/audit |

**team_session.py:**
```python
class TeamSession:
    def create(self, team_name, members, role_budgets) -> str  # returns session_id
    def get_stats(self, session_id, period) -> dict
    def set_role_budget(self, role, limit_usd, period) -> None
    def export_report(self, session_id, format) -> str
```

SQLite-backed (extend existing memory_manager schema). Add tables:
```sql
CREATE TABLE team_sessions (id TEXT PK, team_name TEXT, created_ts REAL);
CREATE TABLE team_members (session_id TEXT, user_id TEXT, role TEXT);
CREATE TABLE role_budgets (session_id TEXT, role TEXT, limit_usd REAL, period TEXT);
```

**Effort:** 2 days

---

## Task F4 — `github_action_check` Dev Tool

| Tool | Inputs | Behaviour |
|------|--------|-----------|
| `github_action_check` | `repo_path?` | Scan `.github/workflows/*.yml` for PromptWise integration hooks; return {integrated: bool, missing_steps: [], suggestions: []} |

Simple YAML parser — no external API needed. Checks if any workflow calls `promptwise-gate` or `promptwise/action`. Suggests where to add it.

**Effort:** 0.5 days

---

## Tool Count After Phase 5F

| Phase | Tools added | Cumulative |
|-------|------------|------------|
| After 5A–5E | — | ~53 |
| F1 Slack+Teams | +2 | ~55 |
| F2 GitHub Actions | +1 (+action.yml) | ~56 |
| F3 Team Session | +4 | ~60 |
| F4 Action Check | +1 | ~61 |
| **Total** | **+8** | **~61** |

---

## Dependencies

New Python packages needed:
```
httpx          # webhook HTTP client (already in pyproject if added)
PyYAML         # already installed
```

No new packages for GitHub API (pure httpx).

---

## Notes for next session

1. Run `python -m pytest tests/ -q` first — confirm green baseline
2. Check `git log --oneline -5` to see last phase completed
3. Start with F1 (webhooks) — smallest, least risky
4. F3 (team sessions) is most complex — do last
5. Keep SQLite for team sessions (not PostgreSQL) — Phase 6+ adds Postgres upgrade path
