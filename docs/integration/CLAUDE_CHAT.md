# Claude Chat Integration

**Status:** ✅ Production-Ready  
**Version:** Claude API v1  
**Last Updated:** June 11, 2026

---

## Overview

PromptWise integrates with Claude API for direct chat and web-based claude.ai access.

**Best for:**
- Direct Claude API calls
- Web-based chat interface (claude.ai)
- Model selection and cost estimation
- Token counting and optimization
- Integration with custom chatbots

---

## Quick Start

### 1. Get API Key

1. Go to [Anthropic Console](https://console.anthropic.com)
2. Create or copy your API key
3. Keep it secret (don't commit to git)

### 2. Set Environment Variable

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or create `.env` file:
```
ANTHROPIC_API_KEY=sk-ant-your_key_here
PROMPTWISE_PLATFORM=claude-chat
```

### 3. Use in Python

```python
from promptwise_v2.adapters import create_adapter
from promptwise_v2.transports import ToolRequest
import asyncio

async def main():
    adapter = create_adapter("claude-chat", {
        "anthropic_api_key": "sk-ant-...",
        "model": "claude-opus-4-7"
    })
    
    request = ToolRequest(
        tool_name="route_request",
        params={
            "text": "Analyze this code for performance issues",
            "intent": "analysis",
            "stakes": "high"
        },
        session_id="session-123"
    )
    
    response = await adapter.call_tool(request)
    print(response.result)

asyncio.run(main())
```

---

## Configuration

### Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | `sk-ant-...` |
| `PROMPTWISE_PLATFORM` | No | `claude-chat` |

### Python Config

```python
config = {
    "anthropic_api_key": "sk-ant-...",
    "model": "claude-opus-4-7",  # Default model
    "timeout_s": 30  # Request timeout
}

adapter = create_adapter("claude-chat", config)
```

---

## Examples

### Example 1: Route to Best Model

```python
response = await adapter.call_tool(ToolRequest(
    tool_name="route_request",
    params={
        "text": "Generate 1000 lines of React component",
        "intent": "coding",
        "stakes": "high",
        "monthly_budget_usd": 50
    },
    session_id="user-abc"
))

# Returns:
# {
#   "recommended_model": "claude-opus-4-7",
#   "reason": "High-stakes code generation",
#   "estimated_input_cost_usd": 0.015,
#   "estimated_output_cost_usd": 0.045
# }
```

### Example 2: Compress Verbose Prompt

```python
response = await adapter.call_tool(ToolRequest(
    tool_name="compress_prompt",
    params={
        "text": "[10KB prompt with redundant instructions]"
    },
    session_id="user-abc"
))

# Returns:
# {
#   "compressed": "[compressed version]",
#   "saving_pct": 35,
#   "tokens_saved": 3500
# }
```

### Example 3: Scan for Security Issues

```python
response = await adapter.call_tool(ToolRequest(
    tool_name="owasp_scan",
    params={
        "code": "const query = `SELECT * FROM users WHERE id = ${userId}`"
    },
    session_id="user-abc"
))

# Returns:
# {
#   "vulnerabilities": [
#     {
#       "category": "A03:2021-SQL Injection",
#       "severity": "critical",
#       "description": "Template string in SQL query"
#     }
#   ],
#   "risk_score": 3,
#   "passed": false
# }
```

---

## Supported Tools

Same as MCP server. All 51 PromptWise tools available:

- route_request
- compress_prompt
- optimize_context
- plan_cache
- batch_prompts
- owasp_scan
- prompt_injection
- security_check
- And 43 more...

See `/skills/SKILL.md` for full reference.

---

## Cost Estimation

PromptWise integrates with Claude's token pricing:

| Model | Input | Output |
|-------|-------|--------|
| claude-haiku-4-5 | $0.0008/1K | $0.0024/1K |
| claude-sonnet-4-6 | $0.003/1K | $0.015/1K |
| claude-opus-4-7 | $0.015/1K | $0.045/1K |

Use `route_request` to get cost estimates before running.

---

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
Set the environment variable:
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key"
```

### "Timeout after 30s"
Increase timeout in config:
```python
adapter = create_adapter("claude-chat", {
    "anthropic_api_key": "sk-ant-...",
    "timeout_s": 60
})
```

### "Model not available"
Check available models at https://console.anthropic.com/docs/api/models

---

## Learn More

- [Multi-Platform Guide](./MULTI_PLATFORM.md)
- [PromptWise Skills](../skills/SKILL.md)
- [Anthropic API Docs](https://docs.anthropic.com)
