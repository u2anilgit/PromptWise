# Integrating PromptWise with Other Tools

**Last Updated:** June 7, 2026  
**Scope:** Generic patterns for integrating with any AI tool or platform

---

## Overview

PromptWise is designed to be a **universal optimization layer** that sits between your application and any LLM provider. This guide covers patterns for integrating with custom tools, internal systems, and third-party platforms.

---

## Architecture Patterns

### Pattern 1: Direct Integration (Recommended)

Use PromptWise as your primary routing/optimization layer:

```
Your Application
    ↓
PromptWise (routing, compression, role detection)
    ↓
[Claude | Codex | Gemini | Custom Tool]
```

**Example:**
```python
from promptwise.adapters import create_adapter
from promptwise.transports import ToolRequest

# Your application
async def analyze_code(code_snippet):
    # 1. Route to best provider
    adapter = create_adapter("gemini", config)
    
    request = ToolRequest(
        tool_name="route_request",
        params={
            "text": code_snippet,
            "intent": "code_analysis"
        },
        session_id="analysis-session"
    )
    
    route_response = await adapter.call_tool(request)
    best_model = route_response.result['recommended_model']
    
    # 2. Use best model (in your application)
    result = call_your_tool(code_snippet, model=best_model)
    
    return result
```

### Pattern 2: Proxy/Middleware

PromptWise as a proxy between your app and external APIs:

```
Your Application
    ↓
PromptWise Proxy (localhost:8765)
├─ Pre-processing: compress, route, validate
├─ API Call: send to provider
└─ Post-processing: validate, track, format
    ↓
External API (OpenAI, Google, etc.)
```

**Setup:**
```python
from fastapi import FastAPI
from promptwise.adapters import create_adapter

app = FastAPI()

@app.post("/api/query")
async def query(text: str, intent: str = "general"):
    adapter = create_adapter("gemini", config)
    
    # PromptWise optimization
    request = ToolRequest(
        tool_name="rewrite_prompt",
        params={"text": text},
        session_id="session-1"
    )
    
    optimized_response = await adapter.call_tool(request)
    optimized_text = optimized_response.result['rewritten_text']
    
    # Your API call (now with optimized text)
    result = call_external_api(optimized_text)
    
    return {"result": result, "optimization": optimized_response.result}
```

### Pattern 3: Plugin/Extension

Integrate as a plugin into an existing tool:

```python
class PromptWisePlugin:
    """Plugin for integrating PromptWise into existing tools."""
    
    def __init__(self, platform="gemini", config=None):
        from promptwise.adapters import create_adapter
        self.adapter = create_adapter(platform, config)
    
    async def optimize_request(self, text, intent):
        """Optimize a request before sending to LLM."""
        from promptwise.transports import ToolRequest
        
        request = ToolRequest(
            tool_name="route_request",
            params={"text": text, "intent": intent},
            session_id="plugin-session"
        )
        
        response = await self.adapter.call_tool(request)
        return response.result
    
    async def get_cost_estimate(self, text):
        """Get cost estimate."""
        from promptwise.transports import ToolRequest
        
        request = ToolRequest(
            tool_name="compare_providers",
            params={"text": text},
            session_id="cost-session"
        )
        
        response = await self.adapter.call_tool(request)
        return response.result['comparison']

# Usage in your tool
plugin = PromptWisePlugin()

# In your tool's API:
optimization = await plugin.optimize_request(user_input, "analysis")
cost_estimate = await plugin.get_cost_estimate(user_input)
```

---

## Integration Recipes

### Recipe 1: LangChain Integration

Use PromptWise to optimize LangChain prompts:

```python
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from promptwise.adapters import create_adapter
from promptwise.transports import ToolRequest
import asyncio

class OptimizedLangChainLLM:
    def __init__(self):
        self.llm = OpenAI(model_name="gpt-4o")
        self.promptwise = create_adapter("gemini", config)
    
    async def __call__(self, prompt_text):
        # Optimize with PromptWise
        request = ToolRequest(
            tool_name="rewrite_prompt",
            params={"text": prompt_text},
            session_id="langchain-session"
        )
        
        response = await self.promptwise.call_tool(request)
        optimized_prompt = response.result['rewritten_text']
        
        # Use with LangChain
        result = self.llm(optimized_prompt)
        
        return result

# Usage
llm = OptimizedLangChainLLM()
result = asyncio.run(llm("Analyze this code for performance issues"))
```

### Recipe 2: Gradio/Streamlit Integration

Use PromptWise in a web interface:

```python
import streamlit as st
from promptwise.adapters import create_adapter
from promptwise.transports import ToolRequest
import asyncio

st.title("Code Analysis with PromptWise Optimization")

# Sidebar: Configuration
platform = st.sidebar.selectbox("Platform", ["mcp", "gemini", "codex"])
intent = st.sidebar.selectbox("Intent", ["analysis", "refactoring", "debugging"])

# Main: Input and output
code_input = st.text_area("Paste your code:")

if st.button("Analyze with PromptWise"):
    adapter = create_adapter(platform, config)
    
    # Get optimization
    optimize_request = ToolRequest(
        tool_name="rewrite_prompt",
        params={"text": code_input},
        session_id="streamlit-session"
    )
    
    optimize_response = asyncio.run(
        adapter.call_tool(optimize_request)
    )
    
    optimized = optimize_response.result['rewritten_text']
    
    # Display results
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Original Prompt**")
        st.code(code_input)
    
    with col2:
        st.write("**Optimized Prompt**")
        st.code(optimized)
    
    # Cost estimate
    compare_request = ToolRequest(
        tool_name="compare_providers",
        params={"text": optimized},
        session_id="streamlit-session"
    )
    
    compare_response = asyncio.run(
        adapter.call_tool(compare_request)
    )
    
    st.write("**Cost Comparison**")
    for option in compare_response.result['comparison']:
        st.metric(
            option['model'],
            f"${option['total_cost_usd']:.6f}"
        )
```

### Recipe 3: API Endpoint Integration

Expose PromptWise as a REST API:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from promptwise.adapters import create_adapter
from promptwise.transports import ToolRequest
import asyncio

app = FastAPI(title="PromptWise API")

class OptimizationRequest(BaseModel):
    text: str
    intent: str = "general"
    stakes: str = "medium"
    budget_usd: float = 1.0

class OptimizationResponse(BaseModel):
    recommended_model: str
    reason: str
    estimated_cost: float
    optimized_text: str

@app.post("/optimize", response_model=OptimizationResponse)
async def optimize(req: OptimizationRequest):
    adapter = create_adapter("gemini", config)
    
    # Route request
    route_request = ToolRequest(
        tool_name="route_request",
        params={
            "text": req.text,
            "intent": req.intent,
            "stakes": req.stakes,
            "budget_usd": req.budget_usd
        },
        session_id="api-session"
    )
    
    route_response = await adapter.call_tool(route_request)
    
    if not route_response.success:
        raise HTTPException(status_code=500, detail=route_response.error)
    
    # Rewrite prompt
    rewrite_request = ToolRequest(
        tool_name="rewrite_prompt",
        params={"text": req.text},
        session_id="api-session"
    )
    
    rewrite_response = await adapter.call_tool(rewrite_request)
    
    return OptimizationResponse(
        recommended_model=route_response.result['recommended_model'],
        reason=route_response.result['reason'],
        estimated_cost=route_response.result['estimated_input_cost_usd'],
        optimized_text=rewrite_response.result['rewritten_text']
    )

# Run: uvicorn script:app --reload
```

### Recipe 4: Celery/Async Task Integration

Use PromptWise with background tasks:

```python
from celery import Celery
from promptwise.adapters import create_adapter
from promptwise.transports import ToolRequest
import asyncio

celery_app = Celery("promptwise_tasks")

@celery_app.task
def optimize_and_analyze(text, intent):
    """Background task: optimize prompt then analyze."""
    
    # Create adapter
    adapter = create_adapter("gemini", config)
    
    async def task():
        # Optimize
        optimize_request = ToolRequest(
            tool_name="rewrite_prompt",
            params={"text": text},
            session_id=f"task-{task.id}"
        )
        
        optimize_response = await adapter.call_tool(optimize_request)
        optimized = optimize_response.result['rewritten_text']
        
        # Get cost estimate
        compare_request = ToolRequest(
            tool_name="compare_providers",
            params={"text": optimized},
            session_id=f"task-{task.id}"
        )
        
        compare_response = await adapter.call_tool(compare_request)
        
        return {
            "original": text,
            "optimized": optimized,
            "cost_estimate": compare_response.result['comparison']
        }
    
    # Run async task
    return asyncio.run(task())

# Usage
task = optimize_and_analyze.delay("Your prompt here", "analysis")
result = task.get()
```

---

## Custom Platform Adapter

Create your own adapter for a custom tool:

```python
from promptwise.transports import TransportAdapter, ToolRequest, ToolResponse
import json
import subprocess

class CustomToolAdapter(TransportAdapter):
    """Adapter for custom internal tool."""
    
    def __init__(self, tool_path="/usr/local/bin/my-tool"):
        super().__init__("custom-tool")
        self.tool_path = tool_path
    
    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """Execute tool via subprocess."""
        
        import time
        start = time.time()
        
        try:
            # Serialize request
            input_json = json.dumps({
                "tool_name": request.tool_name,
                "params": request.params,
                "session_id": request.session_id,
                "context": request.context
            })
            
            # Call tool
            result = subprocess.run(
                [self.tool_path],
                input=input_json,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse response
            if result.returncode != 0:
                return ToolResponse(
                    result={},
                    error=result.stderr,
                    execution_ms=int((time.time() - start) * 1000)
                )
            
            output = json.loads(result.stdout)
            
            return ToolResponse(
                result=output,
                error=None,
                execution_ms=int((time.time() - start) * 1000),
                metadata={"adapter": "custom-tool"}
            )
        
        except Exception as e:
            return ToolResponse(
                result={},
                error=str(e),
                execution_ms=int((time.time() - start) * 1000)
            )
    
    async def health_check(self) -> bool:
        """Check if tool is available."""
        try:
            result = subprocess.run(
                [self.tool_path, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

# Usage
adapter = CustomToolAdapter("/path/to/my-tool")

is_healthy = asyncio.run(adapter.health_check())
if is_healthy:
    response = asyncio.run(adapter.call_tool(request))
```

---

## Configuration Management

### Environment-Based Configuration

```python
import os
from typing import Dict, Any

def load_platform_config() -> Dict[str, Any]:
    """Load configuration from environment."""
    
    platform = os.getenv("PROMPTWISE_PLATFORM", "mcp")
    
    config = {
        "platform": platform,
        "timeout_s": int(os.getenv("PROMPTWISE_TIMEOUT_S", "30")),
        "auto_role": os.getenv("PROMPTWISE_AUTO_ROLE", "true").lower() == "true",
        "log_level": os.getenv("PROMPTWISE_LOG_LEVEL", "INFO")
    }
    
    # Platform-specific config
    if platform == "gemini":
        config["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
    elif platform == "codex":
        config["codex_api_key"] = os.getenv("CODEX_API_KEY")
    elif platform == "antigravity":
        config["antigravity_endpoint"] = os.getenv("ANTIGRAVITY_ENDPOINT")
    
    return config

# Usage
config = load_platform_config()
adapter = create_adapter(config["platform"], config)
```

### YAML Configuration File

```yaml
# promptwise-config.yaml
platforms:
  default: gemini
  
  gemini:
    api_key_env: GEMINI_API_KEY
    timeout: 30
    features:
      auto_role: true
      caching: true
      batching: true
  
  codex:
    api_key_env: CODEX_API_KEY
    timeout: 45
    features:
      auto_role: true
      caching: true
  
  custom_tool:
    endpoint: /path/to/tool
    timeout: 60
    protocol: subprocess

optimization:
  compression_level: light
  batch_size: 3
  cache_ttl_minutes: 60

monitoring:
  track_costs: true
  log_requests: true
  metrics_port: 8000
```

**Load in code:**
```python
import yaml

def load_config(path="promptwise-config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)

config = load_config()
adapter = create_adapter(config['platforms']['default'], config)
```

---

## Testing & Mocking

### Mock Adapter for Testing

```python
from promptwise.transports import TransportAdapter, ToolRequest, ToolResponse

class MockAdapter(TransportAdapter):
    """Mock adapter for testing without real API."""
    
    def __init__(self):
        super().__init__("mock")
        self.calls = []
    
    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """Return mock response based on tool name."""
        
        self.calls.append(request)
        
        mock_responses = {
            "route_request": {
                "recommended_model": "mock-model",
                "reason": "Mock response",
                "estimated_input_cost_usd": 0.001
            },
            "get_session_stats": {
                "total_calls": len(self.calls),
                "total_cost_usd": 0.005,
                "avg_saving_pct": 25.0
            }
        }
        
        result = mock_responses.get(
            request.tool_name,
            {"status": "ok"}
        )
        
        return ToolResponse(result=result, error=None, execution_ms=10)

# Test usage
async def test_workflow():
    adapter = MockAdapter()
    
    request = ToolRequest(
        tool_name="route_request",
        params={"text": "test"},
        session_id="test"
    )
    
    response = await adapter.call_tool(request)
    assert response.success
    assert response.result["recommended_model"] == "mock-model"
    assert len(adapter.calls) == 1

# Run: asyncio.run(test_workflow())
```

---

## Performance Optimization

### Caching Responses

```python
from functools import lru_cache
import hashlib

class CachedAdapter:
    def __init__(self, adapter):
        self.adapter = adapter
        self.cache = {}
    
    def _cache_key(self, request):
        """Generate cache key from request."""
        key_str = f"{request.tool_name}:{request.params}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def call_tool(self, request):
        """Call tool with caching."""
        
        key = self._cache_key(request)
        
        if key in self.cache:
            return self.cache[key]
        
        response = await self.adapter.call_tool(request)
        self.cache[key] = response
        
        return response
    
    def clear_cache(self):
        """Clear cache."""
        self.cache.clear()

# Usage
adapter = CachedAdapter(create_adapter("gemini", config))
response = await adapter.call_tool(request)  # Cached on second call
```

### Batch Processing

```python
async def batch_requests(requests, adapter, batch_size=5):
    """Process requests in batches."""
    
    results = []
    
    for i in range(0, len(requests), batch_size):
        batch = requests[i:i+batch_size]
        
        # Process batch
        batch_responses = await asyncio.gather(*[
            adapter.call_tool(req) for req in batch
        ])
        
        results.extend(batch_responses)
    
    return results

# Usage
requests = [ToolRequest(...) for _ in range(100)]
results = asyncio.run(batch_requests(requests, adapter))
```

---

## Monitoring & Debugging

### Request/Response Logging

```python
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("promptwise")

class LoggingAdapter:
    def __init__(self, adapter):
        self.adapter = adapter
    
    async def call_tool(self, request):
        """Log all requests and responses."""
        
        logger.info(f"→ Request: {request.tool_name}")
        logger.debug(f"  Params: {request.params}")
        
        response = await self.adapter.call_tool(request)
        
        logger.info(f"← Response: {'success' if response.success else 'error'}")
        logger.debug(f"  Execution: {response.execution_ms}ms")
        
        if not response.success:
            logger.error(f"  Error: {response.error}")
        
        return response

# Usage
adapter = LoggingAdapter(create_adapter("gemini", config))
```

---

## Best Practices for Integration

### ✅ DO

- ✅ Use environment variables for secrets
- ✅ Implement proper error handling
- ✅ Log requests and responses
- ✅ Cache responses when appropriate
- ✅ Batch related requests
- ✅ Monitor costs and performance
- ✅ Use async/await for concurrency
- ✅ Implement health checks

### ❌ DON'T

- ❌ Hardcode API keys
- ❌ Ignore errors
- ❌ Make synchronous API calls
- ❌ Send unlimited context
- ❌ Skip authentication
- ❌ Use polling instead of async
- ❌ Cache sensitive data
- ❌ Make assumptions about response format

---

## Support

- **Custom adapter?** See [Custom Platform Adapter](#custom-platform-adapter)
- **Testing?** See [Testing & Mocking](#testing--mocking)
- **Performance?** See [Performance Optimization](#performance-optimization)
- **General help?** See [PORTABILITY.md](PORTABILITY.md)
