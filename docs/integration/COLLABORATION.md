# Claude Collaboration API Integration

**Status:** ✅ Production-Ready  
**Version:** Claude API v1 + Team Extensions  
**Last Updated:** June 11, 2026

---

## Overview

PromptWise Collaboration enables **team/workspace-based** AI workflows with shared contexts, member management, and collaborative sessions.

**Best for:**
- Team-based AI development
- Shared prompt optimization across team
- Workspace-scoped budgets and analytics
- Collaborative debugging and code review
- Multi-user sessions with audit trails

---

## Quick Start

### 1. Get API Keys & IDs

1. Go to [Anthropic Console](https://console.anthropic.com)
2. Create API key
3. Get Team ID from workspace settings
4. Get Workspace ID (optional, for workspace-scoped features)

### 2. Set Environment Variables

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_TEAM_ID="team-..."
export ANTHROPIC_WORKSPACE_ID="ws-..."
```

Or create `.env` file:
```
ANTHROPIC_API_KEY=sk-ant-your_key
ANTHROPIC_TEAM_ID=team-your_id
ANTHROPIC_WORKSPACE_ID=ws-your_id
PROMPTWISE_PLATFORM=collaboration
```

### 3. Use in Python

```python
from promptwise.adapters import create_adapter
from promptwise.transports import ToolRequest
import asyncio

async def main():
    adapter = create_adapter("collaboration", {
        "anthropic_api_key": "sk-ant-...",
        "team_id": "team-...",
        "workspace_id": "ws-..."
    })
    
    # Execute tool in team context
    request = ToolRequest(
        tool_name="route_request",
        params={
            "text": "Code review this PR",
            "intent": "analysis",
            "stakes": "high"
        },
        session_id="session-123",
        context={"shared": True}
    )
    
    response = await adapter.call_tool(request)
    print(response.result)
    
    # Get team members
    members = await adapter.get_team_members()
    print(f"Team: {[m['email'] for m in members]}")
    
    # Share session with team
    await adapter.share_session("session-123", ["alice@company.com", "bob@company.com"])

asyncio.run(main())
```

---

## Configuration

### Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | `sk-ant-...` |
| `ANTHROPIC_TEAM_ID` | Yes | `team-...` |
| `ANTHROPIC_WORKSPACE_ID` | No | `ws-...` |

### Python Config

```python
config = {
    "anthropic_api_key": "sk-ant-...",
    "team_id": "team-abc123",
    "workspace_id": "ws-xyz789",  # Optional
    "timeout_s": 30
}

adapter = create_adapter("collaboration", config)
```

---

## Examples

### Example 1: Team-Scoped Tool Execution

```python
response = await adapter.call_tool(ToolRequest(
    tool_name="route_request",
    params={
        "text": "Optimize this GraphQL query",
        "intent": "coding",
        "stakes": "high"
    },
    session_id="team-session-1",
    context={"shared": True, "team": "engineering"}
))

# Result is visible to all team members with session access
print(response.result["recommended_model"])  # claude-opus-4-7
```

### Example 2: Get Team Members

```python
members = await adapter.get_team_members()

for member in members:
    print(f"{member['email']}: {member['role']} ({member['status']})")

# Output:
# alice@company.com: owner (active)
# bob@company.com: editor (active)
# charlie@company.com: viewer (inactive)
```

### Example 3: Share Session with Team

```python
share_result = await adapter.share_session(
    session_id="session-123",
    user_emails=["alice@company.com", "bob@company.com"]
)

print(f"Shared with {len(share_result['added_users'])} users")
print(f"Access link: {share_result['share_url']}")
```

### Example 4: Get Shared Context

```python
context = await adapter.get_shared_context("session-123")

print(f"Shared by: {context['owner']}")
print(f"Members: {context['members']}")
print(f"Created: {context['created_at']}")
print(f"Last modified: {context['updated_at']}")
```

### Example 5: Update Team Context

```python
adapter.set_team_context(
    team_id="team-new123",
    workspace_id="ws-new456"
)

# All subsequent calls use new team/workspace
response = await adapter.call_tool(request)
```

---

## Team Roles

| Role | Permissions |
|------|-------------|
| owner | Full access, manage members, billing |
| editor | Execute tools, create/modify sessions, manage own shares |
| viewer | View shared sessions, execute read-only tools |
| analyst | Same as editor + analytics/reporting |

---

## Session Sharing

### Share URL Format

```
https://claude.ai/shared/session/[session-id]?token=[share-token]
```

### Share Permissions

```python
# Create shareable link
share_result = await adapter.share_session(
    session_id="session-123",
    user_emails=["alice@company.com"]
)

# Permissions auto-inherited from your role
# Owner shares → recipients get editor role
# Editor shares → recipients get viewer role
```

---

## Audit & Analytics

PromptWise tracks all team activity:

```python
# Get cost report (team-scoped)
response = await adapter.call_tool(ToolRequest(
    tool_name="cost_report",
    params={"period": "monthly", "project_id": "team-123"},
    session_id="admin-session"
))

# Get ROI report (team-scoped)
response = await adapter.call_tool(ToolRequest(
    tool_name="get_roi_report",
    params={"period": "monthly"},
    session_id="admin-session"
))
```

---

## Supported Tools

All 51 PromptWise tools work in collaboration context:

**Execution Tools:**
- route_request
- orchestrate_tasks
- run_autonomous
- batch_prompts

**Optimization Tools:**
- compress_prompt
- optimize_context
- plan_cache

**Security Tools:**
- owasp_scan
- prompt_injection
- security_check

**Analytics Tools:**
- cost_report
- get_roi_report
- monitor_budget

And 40+ more. See `PORTABILITY.md` for full list.

---

## Best Practices

### 1. Session Isolation

Use unique session IDs per user/project:
```python
session_id = f"user-{user_id}-project-{project_id}"
```

### 2. Cost Control

Set team-level budgets:
```python
await adapter.call_tool(ToolRequest(
    tool_name="set_budget_limit",
    params={"limit_usd": 500, "period": "monthly"},
    session_id=f"team-{team_id}-admin"
))
```

### 3. Audit Trail

All shared sessions are logged. Retrieve audit:
```python
context = await adapter.get_shared_context(session_id)
print(context["audit_log"])  # All operations with timestamps/users
```

---

## Troubleshooting

### "Team ID not found"
Get your Team ID from https://console.anthropic.com/account/team

### "Permission denied"
Check your role:
```python
members = await adapter.get_team_members()
me = next(m for m in members if m["is_me"])
print(f"Your role: {me['role']}")
```

### "Session not shared"
Verify share permissions:
```python
context = await adapter.get_shared_context(session_id)
if not context["shared"]:
    share_result = await adapter.share_session(
        session_id,
        ["user@company.com"]
    )
```

---

## Learn More

- [Multi-Platform Guide](./PORTABILITY.md)
- [Claude Chat Integration](./CLAUDE_CHAT.md)
- [Anthropic API Docs](https://docs.anthropic.com)
- [Team Management](https://console.anthropic.com/account/team)
