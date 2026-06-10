# PromptWise Multi-Platform Integration Guide

**Updated:** June 11, 2026  
**Status:** Production-ready for all platforms; MCP (default)

---

## Overview

PromptWise is a unified token-optimization engine that works with multiple AI platforms:

| Platform | Status | Use Case | Models |
|----------|--------|----------|--------|
| **MCP (Claude Code)** | ✅ Default | Local development, Claude Code plugin | Claude Opus/Sonnet/Haiku |
| **Claude API** | ✅ Production | Direct API integration, chatbots | Claude Opus/Sonnet/Haiku |
| **Claude Chat** | ✅ Production | Web-based claude.ai access, direct API | Claude Opus/Sonnet/Haiku |
| **Collaboration** | ✅ Production | Team/workspace workflows, shared sessions | Claude Opus/Sonnet/Haiku |
| **Codex 5.5** | ✅ Production | Code generation, refactoring, multi-file edits | Codex 5.5 base/pro/max |
| **Google Gemini** | ✅ Production | General-purpose AI, reasoning, multimodal | Flash/Pro/Pro-Thinking |
| **Antigravity CLI** | 🔲 Pending | Local agentic tools, internal platforms | Custom |

---

## Quick Start

### 1. Installation

```bash
pip install -e .
```

### 2. Set Environment Variables

```bash
# Choose platform
export PROMPTWISE_PLATFORM=mcp  # or: codex, gemini, antigravity

# Add API keys for your platform(s)
export GEMINI_API_KEY="AIzaSy_your_key"
export CODEX_API_KEY="sk_your_key"
```

### 3. Use in Python

**MCP (Claude Code):**
```python
from promptwise_v2.adapters import create_adapter

adapter = create_adapter("mcp")
```

**Gemini:**
```python
adapter = create_adapter("gemini", {
    "gemini_api_key": "AIzaSy_..."
})
```

**Codex:**
```python
adapter = create_adapter("codex", {
    "codex_api_key": "sk_..."
})
```

### 4. Call a Tool

```python
from promptwise_v2.transports import ToolRequest
import asyncio

async def main():
    adapter = create_adapter("gemini", {
        "gemini_api_key": "AIzaSy_..."
    })
    
    request = ToolRequest(
        tool_name="route_request",
        params={
            "text": "Analyze this 50-page legal document",
            "intent": "analysis",
            "stakes": "high",
            "budget_usd": 0.50
        },
        session_id="session-1"
    )
    
    response = await adapter.call_tool(request)
    print(f"Recommended model: {response.result['recommended_model']}")
    print(f"Estimated cost: ${response.result['estimated_input_cost_usd']}")

asyncio.run(main())
```

---

## Platform-Specific Guides

### [Codex 5.5 Integration](CODEX.md)
- API authentication
- Model tiers (base/pro/max)
- Code-specific optimization
- Example: routing refactoring tasks

### [Gemini Integration](GEMINI.md)
- Google API setup
- Model selection (Flash/Pro)
- Caching strategies
- Example: cost comparison

### MCP (Claude Code)
- Default platform
- Works with Claude Code CLI
- No additional setup required
- See: [Claude Code docs](https://claude.dev/)

### Antigravity CLI
- Requires API specification
- Supports stdio or socket protocols
- See: ANTIGRAVITY.md (when spec available)

---

## Auto-Role Detection

PromptWise automatically detects your role from the prompt and applies context-aware prefixes.

### Detected Roles (16 total)

**Technical:** developer, data, IT, designer, security  
**Business:** manager, analyst, pm, executive  
**Compliance:** legal, healthcare, finance, qa  
**Content:** writer, researcher  
**General:** (fallback)

### Example

```python
from promptwise_v2.core.role_detector import RoleDetector
from promptwise_v2.core.auto_role_applier import AutoRoleApplier

detector = RoleDetector()
applier = AutoRoleApplier(detector, roles_config)

prompt = "Refactor the auth module to use async/await"

result = applier.apply(prompt)
# → Detects: "developer" role (0.95 confidence)
# → Applies: "From a software engineering perspective, ..."
# → Constraints: code_blocks, imports, syntax_validation
```

### Disabling Auto-Role

```bash
export PROMPTWISE_AUTO_ROLE=false
```

Or in code:
```python
config = {
    "auto_role_detection": {"enabled": False}
}
applier = AutoRoleApplier(detector, roles_config, config)
```

---

## Platform Comparison

### Cost Estimation

```python
request = ToolRequest(
    tool_name="compare_providers",
    params={"text": "Analyze this 500-token document"},
    session_id="session-1"
)

response = await adapter.call_tool(request)
# Returns: comparison across Claude, OpenAI, Gemini, Codex
```

**Example output:**
```
Provider    Tier       Model                  Total Cost
gemini      fast       gemini-2.0-flash       $0.00002
codex       fast       codex-5.5-base         $0.00008
claude      fast       haiku-4-5              $0.00035
```

### Performance Characteristics

| Metric | Codex | Gemini | Claude | Best For |
|--------|-------|--------|--------|----------|
| **Latency** | 200-400ms | 150-300ms | 100-250ms | Code gen |
| **Context Window** | 8K-128K | 1M | 200K-1M | Large files |
| **Cost** | Moderate | Very Low | Low-High | Budget |
| **Reasoning** | Good | Excellent | Best | Complex logic |
| **Code** | Best | Good | Good | Refactoring |

---

## Authentication

### Gemini (Google)

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create API key
3. Set environment variable:
   ```bash
   export GEMINI_API_KEY="AIzaSy_..."
   ```

### Codex (OpenAI)

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create API key
3. Set environment variable:
   ```bash
   export CODEX_API_KEY="sk_..."
   ```

### MCP (Claude Code)

- No setup required
- Uses Claude Code's built-in authentication
- Read: [Claude Code docs](https://claude.dev/)

---

## Configuration

### Default Configuration (`config/promptwise_v2.yaml`)

```yaml
platforms:
  default: mcp
  available: [mcp, codex, gemini, antigravity]

auto_role_detection:
  enabled: true
  confidence_threshold: 0.65
  apply_constraints: true
```

### Environment Variables

| Variable | Default | Options |
|----------|---------|---------|
| `PROMPTWISE_PLATFORM` | `mcp` | mcp, codex, gemini, antigravity |
| `PROMPTWISE_AUTO_ROLE` | `true` | true, false |
| `PROMPTWISE_TIMEOUT_S` | `30` | any integer |
| `PROMPTWISE_LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |

---

## Troubleshooting

### "Unknown platform: xyz"

**Problem:** Typo in platform name

**Solution:** Use one of: `mcp`, `codex`, `gemini`, `antigravity`

```python
# ❌ Wrong
adapter = create_adapter("openai")

# ✅ Correct
adapter = create_adapter("codex")
```

### "API key required"

**Problem:** Missing authentication

**Solution:** Set environment variables

```bash
export GEMINI_API_KEY="your-key-here"
# or
export CODEX_API_KEY="your-key-here"
```

### "Connection error: timeout"

**Problem:** API endpoint unreachable

**Solution:** 
- Verify API key is valid
- Check network connectivity
- Check endpoint URL in config
- Increase timeout: `PROMPTWISE_TIMEOUT_S=60`

### "Tool not supported on this platform"

**Problem:** Some tools work better on certain platforms

**Solution:** See platform-specific documentation or use `compare_providers` to find best option

```python
# See which platform is best for this request
request = ToolRequest(
    tool_name="compare_providers",
    params={"text": "your request"},
    session_id="session-1"
)
response = await adapter.call_tool(request)
```

---

## Advanced Usage

### Multi-Platform Routing

Automatically select best platform based on request:

```python
from promptwise_v2.adapters import create_adapter

# Try each platform and compare
platforms = ["codex", "gemini", "claude"]
results = {}

for platform in platforms:
    try:
        adapter = create_adapter(platform, config_for_platform)
        response = await adapter.call_tool(request)
        results[platform] = response
    except Exception as e:
        results[platform] = str(e)

# Choose best result
best = min(results.items(), 
           key=lambda x: x[1].result.get('total_cost_usd', float('inf')))
print(f"Best choice: {best[0]}")
```

### Session Budget Tracking

```python
adapter = create_adapter("gemini", {"gemini_api_key": "..."})

session_budget = 2.00  # $2 limit
session_id = "project-123"

adapter.set_session_context(session_id, {
    "budget": session_budget,
    "model": "gemini-2.0-flash"
})

# Now all calls track against this budget
request = ToolRequest(
    tool_name="route_request",
    params={"text": "...", "budget_usd": session_budget},
    session_id=session_id
)

response = await adapter.call_tool(request)

# Check cost
stats_response = await adapter.call_tool(ToolRequest(
    tool_name="get_session_stats",
    params={},
    session_id=session_id
))

print(f"Total cost: ${stats_response.result['total_cost_usd']}")
```

### Fallback Strategy

```python
async def call_with_fallback(request, primary="gemini", fallback="codex"):
    """Try primary platform, fall back to alternative."""
    
    try:
        adapter = create_adapter(primary, config)
        response = await adapter.call_tool(request)
        if response.success:
            return response
    except Exception as e:
        print(f"{primary} failed: {e}")
    
    # Fall back
    adapter = create_adapter(fallback, config)
    return await adapter.call_tool(request)
```

---

## Metrics & Monitoring

### Track All Calls

```python
# Get session statistics
request = ToolRequest(
    tool_name="get_session_stats",
    params={},
    session_id="session-1"
)

response = await adapter.call_tool(request)

stats = response.result
print(f"Total calls: {stats['total_calls']}")
print(f"Total cost: ${stats['total_cost_usd']}")
print(f"Avg savings: {stats['avg_saving_pct']:.1f}%")
print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
print(f"Model distribution: {stats['cost_by_model']}")
```

### Log All Requests

```bash
export PROMPTWISE_LOG_LEVEL=DEBUG
```

---

## Next Steps

1. **Choose your platform:** See platform-specific guides above
2. **Set API keys:** Add environment variables
3. **Test routing:** Use `route_request` to see recommended models
4. **Monitor costs:** Use `get_session_stats` to track spending
5. **Enable auto-role:** Prompts are optimized per context automatically

---

## Support

- **Documentation:** See individual platform guides
- **Issues:** Check troubleshooting section above
- **Architecture:** See [READINESS_REVIEW.md](../../READINESS_REVIEW.md)
- **Tasks:** See [IMPLEMENTATION_ROADMAP.md](../../IMPLEMENTATION_ROADMAP.md)
