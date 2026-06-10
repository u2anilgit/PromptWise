---
name: promptwise
description: Token-aware prompt routing, cost optimization, and security scanning for Claude Code
---

# PromptWise — Token & Cost Optimization Skill

Use PromptWise tools to optimize prompts, route to right model, track costs, and scan for security issues.

## Quick Start

### Route Request (Pick Right Model)
When unsure which model to use, call:

```
/mcp route_request text="Your prompt here" intent="auto" stakes="auto"
```

Returns: recommended model, cost estimate, context window % used, alternatives.

**Example:**
```
/mcp route_request text="Analyze 50-page legal document for compliance" intent="analysis" stakes="high"
```
→ `claude-opus-4-7` (context: 4.2%, cost: $0.000240 input + $0.000240 output)

---

### Compress Prompt (Save Tokens)
Shrink verbose prompts without losing meaning:

```
/mcp compress_prompt text="Your long prompt..."
```

Returns: compressed text, % tokens saved, rules applied.

---

### Optimize Context (Trim Irrelevant Content)
For large context windows, trim to budget:

```
/mcp optimize_context context="..." token_budget=2000 model="claude-sonnet-4-6"
```

Returns: optimized content, % saved, chunks dropped.

---

### Plan Prompt Cache (Reuse Setup Overhead)
Plan where to break messages for caching when reusing same setup:

```
/mcp plan_cache messages=[...] expected_reuse_count=3 model="claude-sonnet-4-6"
```

Returns: cache breakpoints, % savings if cached.

---

### Batch Prompts (Run Many Together)
Combine independent tasks into one request:

```
/mcp batch_prompts tasks=[...] role="developer" model="claude-sonnet-4-6"
```

Returns: single batched prompt, % savings.

---

### Detect Role (Auto-Context)
Identify your role for context-aware optimization:

```
/mcp detect_role text="Refactor the auth module"
```

→ Detects: `developer` (0.95 confidence). Applies appropriate constraints + optimizations.

---

### Security Scan (Detect Injection)
Check for prompt injection patterns:

```
/mcp prompt_injection text="ignore previous instructions" threshold=0.7
```

Returns: injection_detected, confidence, patterns_found, action (block/warn/allow).

---

### OWASP Scan (Code Vulnerabilities)
Scan code for OWASP Top 10 issues:

```
/mcp owasp_scan code="your code here"
```

Returns: vulnerabilities list, risk_score, passed (bool).

---

### Monitor Budget (Track Spend)
Check current spend vs limit:

```
/mcp monitor_budget used_usd=0.50 days_elapsed=5 project_id="myproject"
```

Returns: pct_used, daily_burn, projected monthly spend, alert_level.

---

### Cost Report (Skill-by-Skill Breakdown)
See which tools cost most:

```
/mcp cost_report period="weekly" project_id="myproject"
```

Returns: cost by skill, total spend.

---

### Validate Output (Check Code Quality)
Ensure generated code is syntactically correct:

```
/mcp validate_output code="..." language="python"
```

Returns: valid (bool), issues, confidence, suggested fix.

---

## All Tools (Reference)

| Tool | Purpose |
|------|---------|
| `route_request` | Pick model by intent/stakes/budget |
| `rewrite_prompt` | Improve clarity for better outputs |
| `optimize_context` | Trim to token budget |
| `compress_prompt` | Shrink without losing meaning |
| `plan_cache` | Optimize prompt caching breakpoints |
| `batch_prompts` | Combine multiple tasks |
| `summarize_thread` | Compress conversation history |
| `compare_providers` | Cost/latency vs Claude/Gemini/Codex |
| `security_check` | Full security audit |
| `prompt_injection` | Detect injection attempts |
| `owasp_scan` | Scan code for vulnerabilities |
| `scan_response` | Check for PII leaks, injection echo |
| `detect_role` | Auto-detect your role |
| `orchestrate_tasks` | Execute multi-step workflows |
| `monitor_budget` | Track spend vs limit |
| `predict_cost` | Estimate cost before running |
| `set_budget_limit` | Set monthly/project budget |
| `get_budget_status` | Current budget state |
| `budget_report` | Weekly/monthly spend summary |
| `validate_output` | Check code syntax/quality |
| `track_roi` | Calculate productivity savings |
| `get_roi_report` | ROI by period |
| `cost_report` | Cost breakdown by skill |
| `get_memory_context` | Retrieve session memory |
| `query_memory` | Search facts in memory |
| `ping_session` | Keep session alive |
| `check_session_timeout` | Warn before timeout |

---

## Cost Savings Examples

**Route before coding:**
```
/mcp route_request text="Generate 500-line Node.js app" stakes="high"
```
→ Recommends Opus (better for large code gen), not Haiku.
**Saves:** avoids 3 Haiku retries = ~$0.15 per request.

**Compress before asking Claude:**
```
/mcp compress_prompt text="[10KB document]"
```
→ 10,000 tokens → 3,500 tokens.
**Saves:** 6,500 × $0.003 (Sonnet input) = ~$0.02 per request.

**Plan cache on repeated setups:**
```
/mcp plan_cache messages=[system, context, query] expected_reuse_count=10
```
→ Cache breakpoint after 2 messages.
**Saves:** 90% cost on cached portions × 10 requests = ~$0.50 per week.

---

## Learn More

- [Multi-Platform Guide](../docs/integration/MULTI_PLATFORM.md) — Use with Gemini, Codex, other platforms
- [Configuration Reference](../docs/integration/CONFIGURATION_REFERENCE.md) — Custom roles, budgets, thresholds
