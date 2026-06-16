# Codex 5.5 Integration Guide

**Status:** ✅ Production-Ready  
**Version:** Codex 5.5  
**Last Updated:** June 7, 2026

---

## Overview

PromptWise provides seamless integration with **OpenAI's Codex 5.5** — a specialized code generation model.

**Best for:**
- Code refactoring and modernization
- Multi-file architectural improvements
- Code generation from specifications
- Complex debugging and optimization
- AI-assisted development workflows

---

## Quick Start

### 1. Get API Key

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create or copy your API key
3. Keep it secret (don't commit to git)

### 2. Set Environment Variable

```bash
export CODEX_API_KEY="sk_..."
```

Or create `.env` file:
```
CODEX_API_KEY=sk_your_key_here
PROMPTWISE_PLATFORM=codex
```

### 3. Use in Python

```python
from promptwise_v2.adapters import create_adapter
from promptwise_v2.transports import ToolRequest
import asyncio

async def main():
    adapter = create_adapter("codex", {
        "codex_api_key": "sk_..."
    })
    
    request = ToolRequest(
        tool_name="route_request",
        params={
            "text": "Refactor this authentication module to use async/await",
            "intent": "refactoring",
            "stakes": "high"
        },
        session_id="session-1"
    )
    
    response = await adapter.call_tool(request)
    print(f"Recommended model: {response.result['recommended_model']}")

asyncio.run(main())
```

---

## Model Tiers

Codex 5.5 offers three tiers optimized for different scenarios:

### Base (Fast)
- **Model:** `codex-5.5-base`
- **Use Case:** Simple code completions, snippets
- **Context Window:** 8K tokens
- **Cost:** $0.80/M input, $3.20/M output
- **Speed:** ~150-200ms

**Example:**
```python
request = ToolRequest(
    tool_name="route_request",
    params={
        "text": "Complete this Python function",
        "intent": "code_completion",
        "stakes": "low"
    },
    session_id="session-1"
)
# → Recommends: codex-5.5-base
```

### Pro (Balanced)
- **Model:** `codex-5.5-pro`
- **Use Case:** Refactoring, debugging, medium-complexity tasks
- **Context Window:** 32K tokens
- **Cost:** $1.80/M input, $7.20/M output
- **Speed:** ~250-350ms

**Example:**
```python
request = ToolRequest(
    tool_name="route_request",
    params={
        "text": "Debug this memory leak in the caching layer",
        "intent": "debugging",
        "stakes": "medium"
    },
    session_id="session-1"
)
# → Recommends: codex-5.5-pro
```

### Max (Powerful)
- **Model:** `codex-5.5-max`
- **Use Case:** Multi-file refactoring, architecture redesign
- **Context Window:** 128K tokens
- **Cost:** $4.50/M input, $18.00/M output
- **Speed:** ~400-600ms

**Example:**
```python
request = ToolRequest(
    tool_name="route_request",
    params={
        "text": "Refactor our entire authentication system to use OAuth 2.0",
        "intent": "refactoring",
        "stakes": "high"
    },
    session_id="session-1"
)
# → Recommends: codex-5.5-max
```

---

## Features

### ✅ Prompt Caching

Save costs on repeated system prompts and context:

```python
request = ToolRequest(
    tool_name="plan_cache",
    params={
        "messages": [
            {"role": "system", "content": "You are a code reviewer..."},  # 500 tokens
            {"role": "user", "content": "Review this code..."}  # 2000 tokens
        ],
        "reuse_count": 100  # How many times this will be reused
    },
    session_id="session-1"
)

response = await adapter.call_tool(request)
# → Returns cache breakpoints
# → First call: 2500 tokens
# → Subsequent 99 calls: ~100 tokens each (2.5K cached)
# → Total savings: ~240K tokens / month
```

### ✅ Batch Processing

Merge related tasks for ~50% cost savings:

```python
request = ToolRequest(
    tool_name="batch_prompts",
    params={
        "tasks": [
            "Refactor function A for readability",
            "Optimize function B for performance",
            "Add type hints to function C"
        ]
    },
    session_id="session-1"
)

response = await adapter.call_tool(request)
# → Returns: merged prompt
# → Cost: ~1 API call instead of 3
```

### ✅ Cost Comparison

See Codex cost vs alternatives:

```python
request = ToolRequest(
    tool_name="compare_providers",
    params={
        "text": "Refactor 2000-token codebase",
        "intent": "refactoring"
    },
    session_id="session-1"
)

response = await adapter.call_tool(request)
# Returns:
# Provider  Model              Cost
# codex     codex-5.5-pro      $0.014
# claude    sonnet-4-6         $0.009  ← Cheaper
# gemini    2.5-pro            $0.003  ← Cheapest
```

### ✅ Output Validation

Automatically check generated code:

```python
from promptwise_v2.core.codex_output_validator import CodexOutputValidator

validator = CodexOutputValidator()

# Codex output
output = """
```python
def calculate_total(items):
    return sum(item.price for item in items)
```
"""

result = validator.validate(output)
print(f"Valid: {result.valid}")
print(f"Issues: {result.issues}")
print(f"Complete: {result.is_complete}")
# → Valid: True
# → Issues: []
# → Complete: True
```

### ✅ Auto-Role Detection

Codex prompts are optimized with `code_specialist` role:

```python
from promptwise_v2.core.auto_role_applier import AutoRoleApplier

applier = AutoRoleApplier(detector, roles_config)

prompt = "Refactor the auth module"
result = applier.apply(prompt)

# → Detects: "developer" role
# → Applies: "From a software engineering perspective, ..."
# → Result: Codex gets better context for code generation
```

---

## Code Generation Examples

### Example 1: Refactoring

```python
request = ToolRequest(
    tool_name="route_request",
    params={
        "text": """
        Refactor this function to use async/await:
        
        def fetch_data(url):
            response = requests.get(url)
            return response.json()
        """,
        "intent": "refactoring",
        "stakes": "medium"
    },
    session_id="session-1"
)

response = await adapter.call_tool(request)
# Recommends: codex-5.5-pro (since refactoring is complex)
```

### Example 2: Multi-File Architecture

```python
request = ToolRequest(
    tool_name="route_request",
    params={
        "text": """
        Refactor these 3 authentication files:
        - auth.py (500 lines)
        - tokens.py (800 lines)
        - permissions.py (600 lines)
        
        Goal: Migrate from session-based to token-based auth
        """,
        "intent": "refactoring",
        "stakes": "high"
    },
    session_id="session-1"
)

response = await adapter.call_tool(request)
# Recommends: codex-5.5-max (multi-file support needed)
```

### Example 3: Debugging

```python
request = ToolRequest(
    tool_name="route_request",
    params={
        "text": """
        Debug this memory leak:
        
        def process_users():
            for user in get_all_users():  # 1M users
                cache[user.id] = user.data  # Memory grows unbounded
        """,
        "intent": "debugging",
        "stakes": "high"
    },
    session_id="session-1"
)

response = await adapter.call_tool(request)
# Recommends: codex-5.5-pro
```

---

## Pricing Breakdown

### Cost per Operation

**Simple completion (100 tokens input, 100 output):**
- Base: $0.00008 + $0.00032 = $0.00040
- Pro:  $0.00018 + $0.00072 = $0.00090
- Max:  $0.00045 + $0.00180 = $0.00225

**Refactoring session (2000 tokens):**
- Base: $0.0016 (with caching: $0.0004)
- Pro:  $0.0036 (with caching: $0.0009)
- Max:  $0.0090 (with caching: $0.0023)

**Monthly estimate (50 refactoring tasks):**
- Without optimization: $0.18
- With caching: $0.045 (75% savings)
- With caching + batching: $0.022 (88% savings)

---

## Cost Optimization Tips

### 1. Use Appropriate Tier

```python
# ❌ Wrong: Using max for simple task
adapter = create_adapter("codex")
request = ToolRequest(
    tool_name="route_request",
    params={
        "text": "Complete this function",
        "intent": "code_completion"  # Should use base tier!
    },
    session_id="session-1"
)

# ✅ Right: Let routing decide
# route_request will recommend base tier automatically
```

### 2. Cache System Prompts

```python
# Reuse coding guidelines across many requests
cache_config = {
    "system_prompt": """
    You are an expert code reviewer.
    - Check for security issues
    - Suggest performance improvements
    - Ensure proper error handling
    """,  # 150 tokens, cached for 5 min
    "ttl_minutes": 5,
    "expected_reuse": 20  # Plan for 20 reviews
}

# After first request, 19 subsequent requests get 90% discount
```

### 3. Batch Related Tasks

```python
# Instead of 3 requests:
tasks = [
    "Add type hints to file A",
    "Add type hints to file B", 
    "Add type hints to file C"
]

# Combine into 1:
batched = batch_prompts(tasks)
# Cost: ~1/3 of separate requests
```

### 4. Compress Context

```python
# Large files don't all matter
request = ToolRequest(
    tool_name="optimize_context",
    params={
        "text": large_file_content,
        "budget_tokens": 4000,  # Limit to 4K
        "priority": ["function_signatures", "docstrings"]  # Keep these
    },
    session_id="session-1"
)

response = await adapter.call_tool(request)
# Returns: compressed version, often 40-60% smaller
```

---

## Monitoring & Metrics

### Track Costs Per Project

```python
# Get session statistics
stats_request = ToolRequest(
    tool_name="get_session_stats",
    params={},
    session_id="auth-refactoring"
)

stats = response.result
print(f"Total cost: ${stats['total_cost_usd']}")
print(f"Cost by model:")
for model, cost in stats['cost_by_model'].items():
    print(f"  {model}: ${cost}")

# Example output:
# Total cost: $0.45
# Cost by model:
#   codex-5.5-base: $0.12
#   codex-5.5-pro:  $0.33
```

### Compare Models

```python
compare_request = ToolRequest(
    tool_name="compare_providers",
    params={
        "text": refactoring_task,
        "intent": "refactoring"
    },
    session_id="session-1"
)

response = await adapter.call_tool(compare_request)

for option in response.result['comparison']:
    if option['provider'] == 'codex':
        print(f"{option['model']}: ${option['total_cost_usd']}")
```

---

## Troubleshooting

### "Invalid API key"

**Problem:** API key is wrong or revoked

**Solution:**
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new key
3. Update environment variable:
   ```bash
   export CODEX_API_KEY="sk_..."
   ```

### "Rate limit exceeded"

**Problem:** Too many requests too quickly

**Solution:**
- Use batch_prompts to merge requests
- Add delays between calls
- Use caching for repeated context
- Upgrade to higher rate limit tier

### "Context window exceeded"

**Problem:** Input is too large for selected model

**Solution:**
- Use optimize_context to compress
- Split into multiple requests
- Use higher tier (e.g., pro → max)

```python
# Compress first
optimize_request = ToolRequest(
    tool_name="optimize_context",
    params={
        "text": large_content,
        "budget_tokens": 30000  # Fit in pro tier
    },
    session_id="session-1"
)

optimized = await adapter.call_tool(optimize_request)
# Now use optimized content with pro tier
```

### "Model not available"

**Problem:** Codex 5.5 not yet released in your region

**Solution:**
- Use Gemini or Claude as fallback
- Check [OpenAI status](https://status.openai.com/)
- Use compare_providers to find alternatives

---

## Advanced Patterns

### Custom Router

```python
def route_to_codex_tier(text, intent, stakes):
    """Determine best Codex tier."""
    
    if "multi-file" in text.lower() or "architecture" in text.lower():
        return "codex-5.5-max"  # 128K context needed
    
    if intent == "refactoring" or stakes == "high":
        return "codex-5.5-pro"   # Safe for complex work
    
    return "codex-5.5-base"      # Default for simple tasks
```

### Fallback Chain

```python
async def refactor_with_fallback(code, budget=2.00):
    """Try Codex first, fall back to cheaper option."""
    
    adapters = [
        ("codex", {"codex_api_key": "sk_..."}),
        ("gemini", {"gemini_api_key": "AIza..."}),
    ]
    
    for platform, config in adapters:
        try:
            adapter = create_adapter(platform, config)
            response = await adapter.call_tool(request)
            
            if response.success and response.result['estimated_cost'] < budget:
                return response
        except Exception as e:
            print(f"{platform} failed: {e}")
            continue
    
    raise Exception("All platforms failed")
```

---

## Next Steps

1. **Get API key** from [OpenAI Platform](https://platform.openai.com/api-keys)
2. **Set environment variable:** `export CODEX_API_KEY="sk_..."`
3. **Test routing:** See which tier is recommended for your task
4. **Monitor costs:** Use `get_session_stats` to track spending
5. **Optimize:** Use caching, batching, compression for 50-90% savings

---

## Support

- **Platform Docs:** https://platform.openai.com/docs/models/codex
- **Status:** https://status.openai.com/
- **Pricing:** https://openai.com/pricing
- **Rate Limits:** See [OpenAI Docs](https://platform.openai.com/docs/guides/rate-limits)
