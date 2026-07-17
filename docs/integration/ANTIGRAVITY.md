# Antigravity CLI Integration Guide

**Status:** 🟡 Ready (awaiting full API specification)  
**Last Updated:** June 7, 2026  
**Architecture:** Proven; tested patterns in place

---

## Overview

PromptWise integrates with **Antigravity CLI** as a local agentic tool platform using stdio or socket communication.

**Use Cases:**
- Internal AI-assisted development workflows
- Local agentic tool chains
- Cost optimization for internal tools
- Multi-provider routing for internal systems

---

## Prerequisites

Before configuring Antigravity integration, you need:

1. **Antigravity CLI installed** on your system
2. **API specification** — Communication protocol details
3. **Authentication method** — Bearer token, OAuth, or custom auth
4. **Endpoint information** — stdio command or socket address

---

## Configuration Options

### Option A: Stdio (Process-Based)

For Antigravity running as a subprocess:

```bash
# .env configuration
export PROMPTWISE_PLATFORM=antigravity
export ANTIGRAVITY_ENDPOINT="stdio:antigravity-server"
export PROMPTWISE_LOG_LEVEL=DEBUG
```

**Python code:**
```python
from promptwise.adapters import create_adapter

adapter = create_adapter("antigravity", {
    "antigravity_endpoint": "stdio:antigravity-server"
})
```

**How it works:**
1. PromptWise spawns subprocess: `antigravity-server`
2. Sends JSON requests via stdin
3. Receives JSON responses via stdout
4. Automatically handles process lifecycle

### Option B: Unix Socket (Local IPC)

For Antigravity listening on a Unix socket:

```bash
# .env configuration
export PROMPTWISE_PLATFORM=antigravity
export ANTIGRAVITY_ENDPOINT="socket:/var/run/antigravity.sock"
```

**Python code:**
```python
adapter = create_adapter("antigravity", {
    "antigravity_endpoint": "/var/run/antigravity.sock"
})
```

**How it works:**
1. Connects to Unix socket at specified path
2. Sends JSON over socket
3. Receives JSON response
4. Persistent connection (auto-reconnect on failure)

### Option C: TCP Socket (Network)

For Antigravity running on local or remote network:

```bash
# .env configuration
export PROMPTWISE_PLATFORM=antigravity
export ANTIGRAVITY_ENDPOINT="socket:localhost:5000"
```

**Or with custom host/port:**
```bash
export ANTIGRAVITY_ENDPOINT="socket:192.168.1.100:8000"
```

**Python code:**
```python
adapter = create_adapter("antigravity", {
    "antigravity_endpoint": "localhost:5000"  # Auto-converts to socket format
})
```

**How it works:**
1. Connects to TCP endpoint
2. Sends/receives JSON over network
3. Ideal for multi-machine setups

---

## Request/Response Protocol

### Request Format

All requests follow PromptWise's unified format:

```json
{
  "tool_name": "string",
  "params": {
    "key": "value"
  },
  "session_id": "string",
  "context": {
    "optional_key": "optional_value"
  }
}
```

**Example:**
```json
{
  "tool_name": "route_request",
  "params": {
    "text": "Analyze this code",
    "intent": "analysis",
    "stakes": "high"
  },
  "session_id": "project-123",
  "context": {
    "file_type": "py",
    "project_type": "api"
  }
}
```

### Response Format

```json
{
  "status": "success|error",
  "result": {
    "key": "value"
  },
  "error": null,
  "execution_time_ms": 150
}
```

**Example:**
```json
{
  "status": "success",
  "result": {
    "recommended_model": "antigravity-pro",
    "reason": "Code analysis recommended",
    "estimated_cost_usd": 0.015
  },
  "error": null,
  "execution_time_ms": 125
}
```

---

## Setup Steps

### Step 1: Install PromptWise

```bash
cd /path/to/PromptWise-1.1.0
pip install -e .
```

### Step 2: Configure Environment

Create `.env` file:

```bash
# Platform
PROMPTWISE_PLATFORM=antigravity

# Endpoint (choose one)
# Stdio: 
ANTIGRAVITY_ENDPOINT="stdio:antigravity-server"

# Unix socket:
# ANTIGRAVITY_ENDPOINT="/var/run/antigravity.sock"

# TCP:
# ANTIGRAVITY_ENDPOINT="localhost:5000"

# Optional settings
PROMPTWISE_LOG_LEVEL=DEBUG
PROMPTWISE_AUTO_ROLE=true
PROMPTWISE_TIMEOUT_S=30
```

### Step 3: Verify Connection

Test connection in Python:

```python
import asyncio
from promptwise.adapters import create_adapter
from promptwise.transports import ToolRequest

async def test_connection():
    adapter = create_adapter("antigravity", {
        "antigravity_endpoint": "socket:localhost:5000"  # Your endpoint
    })
    
    # Health check
    is_healthy = await adapter.health_check()
    print(f"Antigravity healthy: {is_healthy}")
    
    if not is_healthy:
        print("ERROR: Cannot connect to Antigravity")
        return
    
    # Test a simple request
    request = ToolRequest(
        tool_name="get_session_stats",
        params={},
        session_id="test-session"
    )
    
    response = await adapter.call_tool(request)
    print(f"Response: {response.result}")
    print(f"Execution time: {response.execution_ms}ms")

asyncio.run(test_connection())
```

### Step 4: Start PromptWise Server

```bash
# If using as MCP server
python -m promptwise.server

# If using as library
python -c "
from promptwise.adapters import create_adapter
import asyncio

async def main():
    adapter = create_adapter('antigravity', {'antigravity_endpoint': 'localhost:5000'})
    print('PromptWise + Antigravity ready')

asyncio.run(main())
"
```

---

## Usage Examples

### Example 1: Route Request to Antigravity

```python
from promptwise.adapters import create_adapter
from promptwise.transports import ToolRequest
import asyncio

async def route_code_request():
    adapter = create_adapter("antigravity", {
        "antigravity_endpoint": "localhost:5000"
    })
    
    request = ToolRequest(
        tool_name="route_request",
        params={
            "text": "Refactor this authentication module",
            "intent": "refactoring",
            "stakes": "high",
            "budget_usd": 1.00
        },
        session_id="auth-refactor"
    )
    
    response = await adapter.call_tool(request)
    
    if response.success:
        print(f"Recommended model: {response.result['recommended_model']}")
        print(f"Estimated cost: ${response.result['estimated_input_cost_usd']}")
    else:
        print(f"Error: {response.error}")

asyncio.run(route_code_request())
```

### Example 2: Compare Providers (Using Antigravity)

```python
async def compare_providers():
    adapter = create_adapter("antigravity", {
        "antigravity_endpoint": "socket:/tmp/antigravity.sock"
    })
    
    request = ToolRequest(
        tool_name="compare_providers",
        params={
            "text": "Analyze a 500-token document"
        },
        session_id="comparison-test"
    )
    
    response = await adapter.call_tool(request)
    
    if response.success:
        for option in response.result['comparison']:
            print(f"{option['provider']}: ${option['total_cost_usd']}")

asyncio.run(compare_providers())
```

### Example 3: Session Cost Tracking

```python
async def track_session_costs():
    adapter = create_adapter("antigravity", {
        "antigravity_endpoint": "localhost:5000"
    })
    
    session_id = "project-123"
    
    # Set budget
    adapter.set_session_context(session_id, {
        "budget": 2.00,  # $2 limit
        "model": "antigravity-pro"
    })
    
    # Make requests...
    
    # Check costs
    stats_request = ToolRequest(
        tool_name="get_session_stats",
        params={},
        session_id=session_id
    )
    
    response = await adapter.call_tool(stats_request)
    stats = response.result
    
    print(f"Total cost: ${stats['total_cost_usd']}")
    print(f"Total calls: {stats['total_calls']}")
    print(f"Avg savings: {stats['avg_saving_pct']:.1f}%")

asyncio.run(track_session_costs())
```

---

## Auto-Role Detection with Antigravity

PromptWise automatically detects roles and applies optimizations:

```python
from promptwise.core.role_detector import RoleDetector
from promptwise.core.auto_role_applier import AutoRoleApplier

# Create detector and applier
detector = RoleDetector()
roles_config = {...}  # Loaded from roles.yaml
applier = AutoRoleApplier(detector, roles_config)

# Detect and apply
prompt = "Refactor the payment processing module"
result = applier.apply(prompt)

print(f"Detected role: {result['role']}")
print(f"Confidence: {result['confidence']:.0%}")
print(f"Modified prompt: {result['prompt'][:100]}...")

# Use modified prompt with Antigravity
request = ToolRequest(
    tool_name="rewrite_prompt",
    params={"text": result['prompt']},
    session_id="session-1"
)

response = await adapter.call_tool(request)
```

---

## Advanced Configuration

### Multi-Endpoint Setup

Route different tool types to different Antigravity instances:

```python
from promptwise.adapters import create_adapter

class MultiEndpointRouter:
    def __init__(self):
        # Different adapters for different purposes
        self.code_adapter = create_adapter("antigravity", {
            "antigravity_endpoint": "localhost:5000"  # Code analysis instance
        })
        
        self.inference_adapter = create_adapter("antigravity", {
            "antigravity_endpoint": "localhost:5001"  # Inference instance
        })
    
    async def route_request(self, intent, request):
        """Route to appropriate Antigravity instance."""
        
        if intent in ["code_completion", "refactoring", "debugging"]:
            adapter = self.code_adapter
        else:
            adapter = self.inference_adapter
        
        return await adapter.call_tool(request)

# Usage
router = MultiEndpointRouter()
response = await router.route_request("refactoring", request)
```

### Load Balancing

Distribute requests across multiple Antigravity servers:

```python
import asyncio
from typing import List

class LoadBalancedAntigravity:
    def __init__(self, endpoints: List[str]):
        self.adapters = [
            create_adapter("antigravity", {"antigravity_endpoint": ep})
            for ep in endpoints
        ]
        self.current_index = 0
    
    async def call_tool(self, request):
        """Call tool on next available adapter."""
        
        for _ in range(len(self.adapters)):
            adapter = self.adapters[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.adapters)
            
            try:
                response = await adapter.call_tool(request)
                if response.success:
                    return response
            except Exception as e:
                print(f"Adapter failed: {e}")
                continue
        
        raise Exception("All adapters failed")

# Usage
lb = LoadBalancedAntigravity([
    "localhost:5000",
    "localhost:5001",
    "localhost:5002"
])

response = await lb.call_tool(request)
```

### Fallback Strategy

Fall back to other platforms if Antigravity is unavailable:

```python
async def call_with_fallback(request, primary="antigravity", fallback="gemini"):
    """Try primary platform, fall back to alternative."""
    
    try:
        adapter = create_adapter(primary, config)
        response = await adapter.call_tool(request)
        
        if response.success:
            return response, primary
    except Exception as e:
        print(f"{primary} failed: {e}, falling back to {fallback}")
    
    # Fall back
    adapter = create_adapter(fallback, config)
    response = await adapter.call_tool(request)
    return response, fallback

# Usage
response, platform_used = await call_with_fallback(request)
print(f"Used platform: {platform_used}")
```

---

## Troubleshooting

### "Connection refused" Error

**Problem:** Cannot connect to Antigravity endpoint

**Solutions:**

1. **Verify Antigravity is running:**
   ```bash
   # For stdio
   antigravity-server --help
   
   # For socket
   nc -zv localhost 5000
   
   # For Unix socket
   test -S /var/run/antigravity.sock && echo "Socket exists" || echo "Socket missing"
   ```

2. **Check endpoint format:**
   ```python
   # ✅ Correct formats:
   "socket:localhost:5000"
   "/var/run/antigravity.sock"
   "stdio:antigravity-server"
   
   # ❌ Incorrect:
   "localhost:5000"  # Missing 'socket:' prefix
   "antigravity.sock"  # Missing full path
   ```

3. **Increase timeout:**
   ```bash
   export PROMPTWISE_TIMEOUT_S=60
   ```

### "Invalid JSON" Error

**Problem:** Antigravity response is not valid JSON

**Solution:** Verify response format:
```json
{
  "status": "success|error",
  "result": {},
  "error": null,
  "execution_time_ms": 100
}
```

### "Rate limit exceeded" Error

**Problem:** Too many requests too quickly

**Solutions:**
1. Add delays between requests:
   ```python
   import asyncio
   await asyncio.sleep(0.5)  # 500ms delay
   ```

2. Use batching:
   ```python
   request = ToolRequest(
       tool_name="batch_prompts",
       params={"tasks": [task1, task2, task3]},
       session_id="session-1"
   )
   ```

3. Configure rate limits in Antigravity config

### "Timeout" Error

**Problem:** Request takes too long

**Solutions:**
1. Increase timeout:
   ```bash
   export PROMPTWISE_TIMEOUT_S=60
   ```

2. Check Antigravity performance:
   ```python
   # Time individual requests
   import time
   start = time.time()
   response = await adapter.call_tool(request)
   print(f"Took {time.time() - start:.2f}s")
   ```

3. Optimize request size:
   ```python
   request = ToolRequest(
       tool_name="optimize_context",
       params={
           "text": large_content,
           "budget_tokens": 5000
       },
       session_id="session-1"
   )
   ```

---

## Monitoring & Metrics

### Track Antigravity Usage

```python
async def monitor_usage():
    adapter = create_adapter("antigravity", {
        "antigravity_endpoint": "localhost:5000"
    })
    
    # Get session stats
    request = ToolRequest(
        tool_name="get_session_stats",
        params={},
        session_id="session-1"
    )
    
    response = await adapter.call_tool(request)
    stats = response.result
    
    # Print metrics
    print(f"Total requests: {stats['total_calls']}")
    print(f"Total cost: ${stats['total_cost_usd']}")
    print(f"Avg latency: {sum(t['execution_ms'] for t in stats.get('calls', [])) / max(len(stats.get('calls', [])), 1):.0f}ms")
    print(f"Cache hit rate: {stats.get('cache_hit_rate', 0):.1%}")
    print(f"Cost by model:")
    for model, cost in stats['cost_by_model'].items():
        print(f"  {model}: ${cost}")

asyncio.run(monitor_usage())
```

### Real-Time Dashboard

```python
import asyncio
import time

async def live_dashboard():
    adapter = create_adapter("antigravity", {
        "antigravity_endpoint": "localhost:5000"
    })
    
    while True:
        request = ToolRequest(
            tool_name="get_session_stats",
            params={},
            session_id="main"
        )
        
        response = await adapter.call_tool(request)
        stats = response.result
        
        # Clear screen and print stats
        print("\033[2J\033[H")  # Clear
        print(f"PromptWise + Antigravity Dashboard")
        print(f"{'='*50}")
        print(f"Total cost: ${stats['total_cost_usd']:.3f}")
        print(f"Requests: {stats['total_calls']}")
        print(f"Avg savings: {stats['avg_saving_pct']:.1f}%")
        print(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        await asyncio.sleep(5)  # Refresh every 5 seconds

# Run: asyncio.run(live_dashboard())
```

---

## Integration with Other Tools

### Pattern 1: Chained Tools

Use PromptWise output as input to other tools:

```python
async def chained_workflow():
    adapter = create_adapter("antigravity", {...})
    
    # Step 1: Route request via PromptWise
    route_request = ToolRequest(
        tool_name="route_request",
        params={"text": code, "intent": "refactoring"},
        session_id="session-1"
    )
    
    response = await adapter.call_tool(route_request)
    recommended_model = response.result['recommended_model']
    
    # Step 2: Pass to other tool
    other_tool_result = call_other_tool(code, model=recommended_model)
    
    # Step 3: Get session stats
    stats_request = ToolRequest(
        tool_name="get_session_stats",
        params={},
        session_id="session-1"
    )
    
    return other_tool_result, stats

asyncio.run(chained_workflow())
```

### Pattern 2: Integrated Authentication

Manage multiple API keys:

```python
from typing import Dict

class AuthenticatedAntigravity:
    def __init__(self, credentials: Dict[str, str]):
        self.credentials = credentials
        self.adapter = create_adapter("antigravity", {
            "antigravity_endpoint": "localhost:5000"
        })
    
    async def call_authenticated(self, request, auth_type="bearer"):
        """Call Antigravity with authentication."""
        
        # Add auth to request context
        request.context = request.context or {}
        request.context['auth_type'] = auth_type
        request.context['api_key'] = self.credentials.get(auth_type)
        
        return await self.adapter.call_tool(request)

# Usage
auth = AuthenticatedAntigravity({
    "bearer": "token_xyz",
    "basic": "user:pass"
})

response = await auth.call_authenticated(request, auth_type="bearer")
```

---

## Best Practices

### ✅ DO

- ✅ Use appropriate endpoint type (stdio for subprocess, socket for network)
- ✅ Set reasonable timeouts based on your workload
- ✅ Monitor costs with `get_session_stats`
- ✅ Implement fallback to other platforms
- ✅ Use auto-role detection for optimization
- ✅ Batch related requests
- ✅ Cache system prompts for repeated work

### ❌ DON'T

- ❌ Hardcode API keys (use environment variables)
- ❌ Make requests without session_id (breaks cost tracking)
- ❌ Ignore errors (implement proper error handling)
- ❌ Send unlimited context (use `optimize_context`)
- ❌ Make synchronous API calls in async code
- ❌ Skip health checks on startup

---

## Next Steps

1. **Get API Spec** — Request complete Antigravity API documentation
2. **Set Up Endpoint** — Configure stdio, Unix socket, or TCP endpoint
3. **Test Connection** — Verify connectivity with health check
4. **Enable Auto-Role** — Let PromptWise optimize prompts automatically
5. **Monitor Usage** — Track costs and performance

---

## Support

For issues or questions:

- **Connection problems?** See [Troubleshooting](#troubleshooting)
- **Protocol questions?** Check [Request/Response Format](#requestresponse-protocol)
- **General setup?** See [Multi-Platform Guide](PORTABILITY.md)
- **Architecture?** See [READINESS_REVIEW.md](../../READINESS_REVIEW.md)
