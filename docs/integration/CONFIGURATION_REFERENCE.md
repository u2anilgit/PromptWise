# PromptWise Configuration Reference

**Quick lookup for all configuration options and how to use them**

---

## Environment Variables

### Platform Selection

```bash
# Choose platform: mcp (default), codex, gemini, antigravity
export PROMPTWISE_PLATFORM=gemini
```

### API Keys

```bash
# Google Gemini
export GEMINI_API_KEY="AIzaSy_..."

# OpenAI Codex
export CODEX_API_KEY="sk_..."

# Antigravity CLI
export ANTIGRAVITY_ENDPOINT="localhost:5000"
```

### Auto-Role Detection

```bash
# Enable/disable auto-role detection (default: true)
export PROMPTWISE_AUTO_ROLE=true

# Confidence threshold for role detection (default: 0.65)
export PROMPTWISE_AUTO_ROLE_THRESHOLD=0.65
```

### Timeouts & Performance

```bash
# Request timeout in seconds (default: 30)
export PROMPTWISE_TIMEOUT_S=60

# Session budget in USD (optional)
export PROMPTWISE_SESSION_BUDGET=5.00
```

### Logging & Debug

```bash
# Log level: DEBUG, INFO (default), WARNING, ERROR
export PROMPTWISE_LOG_LEVEL=DEBUG

# Save session history (default: false)
export PROMPTWISE_SAVE_HISTORY=true
```

---

## Configuration Files

### `.env` File (Recommended)

```bash
# Copy .env.example to .env and fill in your values

# Platform
PROMPTWISE_PLATFORM=gemini

# API Keys
GEMINI_API_KEY=AIzaSy_your_key
CODEX_API_KEY=sk_your_key

# Optional
PROMPTWISE_TIMEOUT_S=45
PROMPTWISE_AUTO_ROLE=true
PROMPTWISE_LOG_LEVEL=INFO
```

**Load automatically:**
```python
from dotenv import load_dotenv
load_dotenv()

# Now all env vars are available
import os
platform = os.getenv("PROMPTWISE_PLATFORM", "mcp")
```

### `config/promptwise.yaml`

Main configuration file with platform and feature settings:

```yaml
platforms:
  default: mcp
  available: [mcp, codex, gemini, antigravity]
  
  mcp:
    enabled: true
  
  codex:
    enabled: true
    api_endpoint: "https://api.openai.com/v1"
  
  gemini:
    enabled: true
    api_endpoint: "https://generativelanguage.googleapis.com/v1beta/models"
  
  antigravity:
    enabled: false  # Enable when API spec ready

auto_role_detection:
  enabled: true
  confidence_threshold: 0.65
  apply_constraints: true
```

### `config/role_keywords.yaml`

Role definitions for auto-detection:

```yaml
roles:
  developer:
    keywords: [refactor, debug, code, function, api, ...]
    patterns: ["def\\s+\\w+", "class\\s+\\w+", ...]
    weight: 1.0
  
  analyst:
    keywords: [metrics, data, report, trend, ...]
    patterns: ["SELECT\\s+", ...]
    weight: 0.95
  
  # ... 14 more roles
```

**Don't edit this file unless adding new roles.**

### `pricing.yaml`

Model pricing and configuration:

```yaml
models:
  claude-sonnet-4-6:
    provider: claude
    tier: balanced
    rates:
      input_per_mtok: 3.00
      output_per_mtok: 15.00
      cache_write_5m_per_mtok: 3.75
  
  codex-5.5-pro:
    provider: codex
    tier: balanced
    rates:
      input_per_mtok: 1.80
      output_per_mtok: 7.20
  
  # ... other models
```

**Update when prices change:**
```bash
# Update last_verified date
last_verified: "2026-06-07"
```

### `providers.yaml`

Provider definitions and features:

```yaml
providers:
  claude:
    display_name: "Anthropic Claude"
    tiers:
      fast: claude-haiku-4-5
      balanced: claude-sonnet-4-6
      powerful: claude-opus-4-7
  
  codex:
    display_name: "OpenAI Codex 5.5"
    tiers:
      fast: codex-5.5-base
      balanced: codex-5.5-pro
      powerful: codex-5.5-max
    features:
      supports_caching: true
      supports_batching: true
```

---

## Python Configuration

### Minimal Setup

```python
from promptwise.adapters import create_adapter

# Use defaults (MCP)
adapter = create_adapter("mcp")
```

### With API Key

```python
# Gemini
adapter = create_adapter("gemini", {
    "gemini_api_key": "AIzaSy_..."
})

# Codex
adapter = create_adapter("codex", {
    "codex_api_key": "sk_..."
})

# Antigravity
adapter = create_adapter("antigravity", {
    "antigravity_endpoint": "localhost:5000"
})
```

### Full Configuration

```python
from promptwise.adapters import create_adapter
from promptwise.core.role_detector import RoleDetector
from promptwise.core.auto_role_applier import AutoRoleApplier

# Create adapter
adapter = create_adapter("gemini", {
    "gemini_api_key": "AIzaSy_...",
    "timeout_s": 45
})

# Setup auto-role detection
detector = RoleDetector()
roles_config = {...}  # Load from roles.yaml
applier = AutoRoleApplier(
    detector, 
    roles_config,
    {
        "enabled": True,
        "confidence_threshold": 0.65,
        "apply_constraints": True
    }
)

# Use adapter
request = ToolRequest(...)
response = await adapter.call_tool(request)

# Apply auto-role
role_result = applier.apply("your prompt")
```

---

## Platform-Specific Setup

### MCP (Claude Code) — Default

**No setup needed. It just works.**

```bash
# Nothing to configure
python -m promptwise.server
```

### Gemini (Google)

```bash
# 1. Get API key from https://aistudio.google.com/app/apikey
# 2. Set environment
export GEMINI_API_KEY="AIzaSy_..."
export PROMPTWISE_PLATFORM=gemini

# 3. Run
python -m promptwise.server
```

**Features:**
- ✅ Prompt caching
- ✅ Batching
- ✅ Multiple tiers (Flash, Pro, Pro-Thinking)
- ✅ Cost comparison

### Codex 5.5 (OpenAI)

```bash
# 1. Get API key from https://platform.openai.com/api-keys
# 2. Set environment
export CODEX_API_KEY="sk_..."
export PROMPTWISE_PLATFORM=codex

# 3. Run
python -m promptwise.server
```

**Features:**
- ✅ Code-specialized models
- ✅ 3 tiers (base, pro, max)
- ✅ Multi-file refactoring support
- ✅ Output validation

### Antigravity CLI

```bash
# 1. Install/start Antigravity
antigravity-server &

# 2. Set environment (choose one)
export ANTIGRAVITY_ENDPOINT="stdio:antigravity-server"  # Stdio
export ANTIGRAVITY_ENDPOINT="/var/run/antigravity.sock"  # Unix socket
export ANTIGRAVITY_ENDPOINT="localhost:5000"              # TCP

# 3. Run
python -m promptwise.server
```

**Features:**
- ✅ Local integration
- ✅ Multiple communication protocols
- ✅ Load balancing support
- ✅ Fallback to other platforms

---

## Common Configuration Scenarios

### Scenario 1: Development (Local, Fast Iteration)

```bash
# .env
PROMPTWISE_PLATFORM=mcp
PROMPTWISE_LOG_LEVEL=DEBUG
PROMPTWISE_AUTO_ROLE=true
```

### Scenario 2: Production (High Quality, Cost-Optimized)

```bash
# .env
PROMPTWISE_PLATFORM=gemini
GEMINI_API_KEY=AIzaSy_...
PROMPTWISE_AUTO_ROLE=true
PROMPTWISE_SESSION_BUDGET=10.00
PROMPTWISE_TIMEOUT_S=60
PROMPTWISE_LOG_LEVEL=INFO
```

### Scenario 3: Code Generation (Codex Specialist)

```bash
# .env
PROMPTWISE_PLATFORM=codex
CODEX_API_KEY=sk_...
PROMPTWISE_AUTO_ROLE=true
```

### Scenario 4: Internal Tool (Antigravity)

```bash
# .env
PROMPTWISE_PLATFORM=antigravity
ANTIGRAVITY_ENDPOINT=localhost:5000
PROMPTWISE_AUTO_ROLE=true
PROMPTWISE_TIMEOUT_S=45
```

### Scenario 5: Multi-Platform Routing

```python
# Don't set PROMPTWISE_PLATFORM
# Instead, choose at runtime

from promptwise.adapters import create_adapter

def get_best_adapter(task_type):
    if task_type == "code":
        return create_adapter("codex", config)
    elif task_type == "analysis":
        return create_adapter("gemini", config)
    else:
        return create_adapter("mcp")
```

---

## Endpoint Formats

### Stdio (Process-Based)

```bash
export ANTIGRAVITY_ENDPOINT="stdio:command-name"
export ANTIGRAVITY_ENDPOINT="stdio:/path/to/tool"

# Examples:
export ANTIGRAVITY_ENDPOINT="stdio:antigravity-server"
export ANTIGRAVITY_ENDPOINT="stdio:/usr/local/bin/my-tool"
```

### Unix Socket

```bash
export ANTIGRAVITY_ENDPOINT="/path/to/socket.sock"
export ANTIGRAVITY_ENDPOINT="socket:/var/run/antigravity.sock"

# Examples:
export ANTIGRAVITY_ENDPOINT="/var/run/antigravity.sock"
export ANTIGRAVITY_ENDPOINT="socket:/tmp/my-tool.sock"
```

### TCP Socket

```bash
export ANTIGRAVITY_ENDPOINT="host:port"
export ANTIGRAVITY_ENDPOINT="socket:host:port"

# Examples:
export ANTIGRAVITY_ENDPOINT="localhost:5000"
export ANTIGRAVITY_ENDPOINT="socket:192.168.1.100:8000"
export ANTIGRAVITY_ENDPOINT="api.example.com:443"
```

---

## Configuration Validation

### Check Configuration

```python
import os
from promptwise.adapters import get_default_platform

# Check platform
platform = os.getenv("PROMPTWISE_PLATFORM", "mcp")
print(f"Platform: {platform}")

# Check API key
if platform == "gemini":
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set")
    else:
        print("✓ GEMINI_API_KEY is set")

# Try to create adapter
try:
    from promptwise.adapters import create_adapter
    adapter = create_adapter(platform)
    print("✓ Adapter created successfully")
except Exception as e:
    print(f"✗ Failed to create adapter: {e}")
```

### Test Connection

```python
import asyncio
from promptwise.adapters import create_adapter

async def test_connection():
    adapter = create_adapter("gemini", {"gemini_api_key": "..."})
    
    is_healthy = await adapter.health_check()
    
    if is_healthy:
        print("✓ Connection successful")
    else:
        print("✗ Connection failed")

asyncio.run(test_connection())
```

---

## Troubleshooting Configuration

### "Platform not found"

```
Error: Unknown platform: xyz

Solution: Check PROMPTWISE_PLATFORM value
Supported: mcp, codex, gemini, antigravity
```

### "API key required"

```
Error: Codex API key required. Set CODEX_API_KEY env var

Solution:
export CODEX_API_KEY="sk_..."
```

### "Connection refused"

```
Error: Cannot connect to endpoint

Solutions:
1. Verify endpoint format: "socket:localhost:5000"
2. Verify service is running
3. Increase timeout: PROMPTWISE_TIMEOUT_S=60
```

### "Configuration file not found"

```
Error: Cannot load config/promptwise.yaml

Solution:
1. Make sure you're in the PromptWise directory
2. Check file exists: ls config/promptwise.yaml
3. Check permissions: chmod 644 config/promptwise.yaml
```

---

## Configuration Best Practices

### ✅ DO

- ✅ Use `.env` file for secrets
- ✅ Set `PROMPTWISE_AUTO_ROLE=true` for optimization
- ✅ Use appropriate timeout based on workload
- ✅ Set `PROMPTWISE_SESSION_BUDGET` to limit costs
- ✅ Use `PROMPTWISE_LOG_LEVEL=DEBUG` in development
- ✅ Validate configuration on startup
- ✅ Document your configuration choices
- ✅ Keep pricing.yaml updated

### ❌ DON'T

- ❌ Hardcode API keys in code
- ❌ Commit `.env` to git
- ❌ Use very short timeouts (<10s)
- ❌ Disable auto-role without reason
- ❌ Forget to set required env vars
- ❌ Mix configuration sources (env + files)
- ❌ Share API keys
- ❌ Use outdated pricing data

---

## Advanced Configuration

### Multi-Environment Setup

```bash
# development.env
PROMPTWISE_PLATFORM=mcp
PROMPTWISE_LOG_LEVEL=DEBUG

# staging.env
PROMPTWISE_PLATFORM=gemini
GEMINI_API_KEY=...
PROMPTWISE_LOG_LEVEL=INFO

# production.env
PROMPTWISE_PLATFORM=gemini
GEMINI_API_KEY=...
PROMPTWISE_SESSION_BUDGET=100.00
PROMPTWISE_LOG_LEVEL=WARNING
```

**Load the right file:**
```bash
export ENV=production
source ${ENV}.env
python -m promptwise.server
```

### Dynamic Configuration

```python
import os
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """Load configuration from multiple sources."""
    
    config = {
        "platform": os.getenv("PROMPTWISE_PLATFORM", "mcp"),
        "timeout_s": int(os.getenv("PROMPTWISE_TIMEOUT_S", "30")),
        "auto_role": os.getenv("PROMPTWISE_AUTO_ROLE", "true").lower() == "true",
    }
    
    # Platform-specific
    if config["platform"] == "gemini":
        config["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
    elif config["platform"] == "codex":
        config["codex_api_key"] = os.getenv("CODEX_API_KEY")
    elif config["platform"] == "antigravity":
        config["antigravity_endpoint"] = os.getenv("ANTIGRAVITY_ENDPOINT")
    
    return config

config = load_config()
```

---

## Summary

| Aspect | How To Configure |
|--------|-----------------|
| **Platform** | `export PROMPTWISE_PLATFORM=gemini` |
| **API Keys** | `export GEMINI_API_KEY="..."` |
| **Auto-Role** | `export PROMPTWISE_AUTO_ROLE=true` |
| **Timeout** | `export PROMPTWISE_TIMEOUT_S=45` |
| **Logging** | `export PROMPTWISE_LOG_LEVEL=DEBUG` |
| **Python** | `create_adapter("platform", config)` |
| **Validation** | Run health check or test request |

For detailed information on each platform, see:
- [PORTABILITY.md](PORTABILITY.md) — All platforms overview
- [CODEX.md](CODEX.md) — Codex-specific setup
- [ANTIGRAVITY.md](ANTIGRAVITY.md) — Antigravity setup
- [OTHER_TOOLS.md](OTHER_TOOLS.md) — Custom tool integration
