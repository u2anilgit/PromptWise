# PromptWise Multi-Platform Integration — Implementation Roadmap

**Prepared for:** Multi-platform deployment (Codex, Gemini, Antigravity CLI)  
**Status:** Ready for Phase 1 kickoff  
**Timeline:** 4-6 weeks to production readiness (2 engineers recommended)

---

## QUICK START: What Needs to Be Built

**3 critical pieces before multi-platform shipping:**

1. **Transport Adapter Layer** (2 weeks)
   - Abstract MCP away; support HTTP, CLI, and custom protocols
   - Enable Codex/Gemini/Antigravity direct API calls

2. **Auto-Role Detection** (1.5 weeks)
   - Infer role from request context automatically
   - Apply role-specific prefixes and constraints

3. **Optimization Profiles** (1.5 weeks)
   - Model-specific tuning (Gemini Flash vs Claude Haiku, etc.)
   - Platform-specific compression/caching strategies

**Don't start Phase A tools yet.** Designs are complete, but not critical for multi-platform integration.

---

## PHASE 1: FOUNDATION (Weeks 1-2)

### Task 1.1: Multi-Platform Adapter Pattern (5 days)

**Goal:** Decouple PromptWise core from MCP; support HTTP, CLI, and custom transports.

**Files to create:**

1. **`src/promptwise_v2/transports/__init__.py`**
   ```python
   from abc import ABC, abstractmethod
   from dataclasses import dataclass
   from typing import Optional, Dict, Any
   
   @dataclass
   class ToolRequest:
       tool_name: str
       params: Dict[str, Any]
       session_id: str
       context: Optional[Dict] = None
   
   @dataclass
   class ToolResponse:
       result: Dict[str, Any]
       error: Optional[str] = None
       execution_ms: int = 0
   
   class TransportAdapter(ABC):
       """Base class for all platform transports (MCP, HTTP, CLI, etc)."""
       
       @abstractmethod
       async def call_tool(self, request: ToolRequest) -> ToolResponse:
           """Execute a tool and return result."""
           pass
       
       @abstractmethod
       def set_session_context(self, session_id: str, context: Dict) -> None:
           """Set session-level config (budget, model preference, etc)."""
           pass
       
       def start(self) -> None:
           """Lifecycle hook: server startup."""
           pass
       
       def stop(self) -> None:
           """Lifecycle hook: server shutdown."""
           pass
   ```

2. **`src/promptwise_v2/transports/mcp_adapter.py`**
   ```python
   from . import TransportAdapter, ToolRequest, ToolResponse
   from ..integrations.mcp_server_v2 import ServerContextV2, call_tool_v2
   
   class MCPAdapter(TransportAdapter):
       """Existing MCP server wrapped as a transport."""
       
       def __init__(self):
           self.context = ServerContextV2()
       
       async def call_tool(self, request: ToolRequest) -> ToolResponse:
           try:
               result = await call_tool_v2(
                   self.context, 
                   request.tool_name, 
                   request.params
               )
               return ToolResponse(result=result)
           except Exception as e:
               return ToolResponse(result={}, error=str(e))
       
       def set_session_context(self, session_id: str, context: Dict) -> None:
           self.context.session_id = session_id
           self.context.session_budget = context.get("budget", 1.0)
           self.context.preferred_model = context.get("model")
   ```

3. **`src/promptwise_v2/transports/http_adapter.py`**
   ```python
   from . import TransportAdapter, ToolRequest, ToolResponse
   import httpx
   
   class HTTPAdapter(TransportAdapter):
       """Generic HTTP transport for REST APIs (Codex, Gemini, etc)."""
       
       def __init__(self, base_url: str, api_key: str, provider: str):
           self.base_url = base_url
           self.api_key = api_key
           self.provider = provider
           self.client = httpx.AsyncClient()
       
       async def call_tool(self, request: ToolRequest) -> ToolResponse:
           # Route to provider-specific method
           if self.provider == "codex":
               return await self._call_codex(request)
           elif self.provider == "gemini":
               return await self._call_gemini(request)
           else:
               return ToolResponse(result={}, error=f"Unknown provider: {self.provider}")
       
       async def _call_codex(self, request: ToolRequest) -> ToolResponse:
           headers = {"Authorization": f"Bearer {self.api_key}"}
           # Map promptwise tool → Codex API call
           # E.g., route_request → GET /models with params
           ...
       
       async def _call_gemini(self, request: ToolRequest) -> ToolResponse:
           # Map to Gemini's generativelanguage.googleapis.com API
           ...
   ```

4. **`src/promptwise_v2/transports/cli_adapter.py`**
   ```python
   from . import TransportAdapter, ToolRequest, ToolResponse
   import json
   import asyncio
   
   class CLIAdapter(TransportAdapter):
       """Generic CLI transport for tools like Antigravity."""
       
       def __init__(self, endpoint: str):
           self.endpoint = endpoint  # e.g., "localhost:5000" or "/var/run/antigravity.sock"
       
       async def call_tool(self, request: ToolRequest) -> ToolResponse:
           # Serialize request to JSON, send to endpoint, parse response
           ...
   ```

5. **`src/promptwise_v2/adapters/__init__.py`**
   ```python
   from .transports import TransportAdapter
   
   def create_adapter(platform: str, config: dict) -> TransportAdapter:
       """Factory: instantiate the right adapter."""
       
       if platform == "mcp":
           from .transports.mcp_adapter import MCPAdapter
           return MCPAdapter()
       
       elif platform == "codex":
           from .transports.http_adapter import HTTPAdapter
           return HTTPAdapter(
               base_url="https://api.openai.com/v1",  # Codex endpoint
               api_key=config.get("codex_api_key"),
               provider="codex"
           )
       
       elif platform == "gemini":
           from .transports.http_adapter import HTTPAdapter
           return HTTPAdapter(
               base_url="https://generativelanguage.googleapis.com/v1beta/models",
               api_key=config.get("gemini_api_key"),
               provider="gemini"
           )
       
       elif platform == "antigravity":
           from .transports.cli_adapter import CLIAdapter
           return CLIAdapter(
               endpoint=config.get("antigravity_endpoint")
           )
       
       else:
           raise ValueError(f"Unknown platform: {platform}")
   ```

**Tests to write:**

- `tests/v2/transports/test_mcp_adapter.py` — Verify existing MCP server works via adapter
- `tests/v2/transports/test_http_adapter.py` — Mock HTTP responses; test Codex/Gemini routing
- `tests/v2/transports/test_cli_adapter.py` — Mock stdio/socket; test Antigravity routing
- `tests/v2/test_adapter_factory.py` — Verify factory creates correct adapter per platform

**Checklist:**
- [ ] Define `TransportAdapter` ABC and `ToolRequest`/`ToolResponse` dataclasses
- [ ] Implement `MCPAdapter` wrapping existing server
- [ ] Implement `HTTPAdapter` (generic REST with provider-specific methods)
- [ ] Implement `CLIAdapter` (generic stdio/socket with endpoint config)
- [ ] Implement `create_adapter()` factory
- [ ] Write 20+ integration tests (mock endpoints)
- [ ] Update `pyproject.toml` — add `httpx` dependency if not present
- [ ] Document in README: "Supported platforms: MCP, Codex, Gemini, Antigravity"

**Estimated effort:** 5 days (1 person)

---

### Task 1.2: Auto-Role Detection (5 days)

**Goal:** Infer role from request context; apply role-specific prefixes and constraints.

**Files to create:**

1. **`src/promptwise_v2/core/role_detector.py`**
   ```python
   from typing import List, Tuple
   from dataclasses import dataclass
   
   @dataclass
   class RoleDetectionResult:
       primary_role: str          # Highest confidence
       confidence: float          # 0.0-1.0
       secondary_roles: List[Tuple[str, float]]  # [(role, confidence), ...]
       keywords_matched: List[str]
       rationale: str
   
   class RoleDetector:
       """Infer role from prompt/context using keyword matching + NLP."""
       
       def __init__(self, roles_config: dict):
           """
           roles_config: {
             "developer": {"keywords": [...], "patterns": [...]},
             "analyst": {...},
             ...
           }
           """
           self.roles_config = roles_config
           self._build_keyword_index()
       
       def _build_keyword_index(self):
           """Pre-compute TF-IDF weights for role keywords."""
           self.role_keywords = {
               "developer": {
                   "keywords": ["refactor", "debug", "code", "function", "api", "library",
                              "bug", "issue", "fix", "test", "import", "module"],
                   "patterns": [r"def\s+\w+", r"class\s+\w+"],  # regex for code signatures
                   "weight": 1.0
               },
               "analyst": {
                   "keywords": ["metrics", "data", "report", "trend", "aggregat", "average",
                              "sum", "count", "compare", "analyze", "pivot", "dashboard"],
                   "patterns": [r"SELECT\s+", r"aggregat", r"GROUP BY"],
                   "weight": 0.9
               },
               "manager": {
                   "keywords": ["timeline", "roadmap", "priorit", "capacity", "velocity",
                              "sprint", "plan", "stakeholder", "decision", "strategy"],
                   "patterns": [r"Q[1-4]\s+20\d{2}"],
                   "weight": 0.8
               },
               "security": {
                   "keywords": ["auth", "encrypt", "vulnerability", "compliance", "gdpr",
                              "ccpa", "pii", "threat", "risk", "penetrat", "exploit"],
                   "patterns": [r"CVE-\d+", r"OWASP"],
                   "weight": 1.0
               },
               "IT": {
                   "keywords": ["deploy", "infra", "scaling", "failover", "cloud", "aws",
                              "kubernetes", "docker", "ci/cd", "terraform", "ansible"],
                   "patterns": [r"kubectl", r"docker\s+run", r"terraform\s+apply"],
                   "weight": 0.95
               },
               # ... 12 more roles
           }
       
       def detect(self, prompt: str, context: dict = None) -> RoleDetectionResult:
           """
           Analyze prompt and optional context; return top role + alternates.
           
           context (optional):
               - file_type: "sql", "py", "yaml", "md"
               - project_type: "api", "ml", "infra", "data"
               - recent_context: [previous 3-5 messages]
           """
           
           # Tokenize and normalize prompt
           prompt_lower = prompt.lower()
           tokens = prompt_lower.split()
           
           # Score each role
           scores = {}
           for role, config in self.role_keywords.items():
               score = 0.0
               matched = []
               
               # Keyword matching
               for kw in config["keywords"]:
                   for token in tokens:
                       if kw in token or token in kw:
                           score += 1.0
                           matched.append(kw)
               
               # Pattern matching (regex)
               import re
               for pattern in config["patterns"]:
                   if re.search(pattern, prompt_lower):
                       score += 2.0
                       matched.append(f"pattern:{pattern}")
               
               # Normalize by role's keyword count
               score = (score / max(len(config["keywords"]), 1)) * config["weight"]
               scores[role] = (score, matched)
           
           # Rank roles by confidence
           ranked = sorted(scores.items(), key=lambda x: x[1][0], reverse=True)
           
           primary_role, (confidence, keywords) = ranked[0]
           secondary_roles = [(role, score) for role, (score, _) in ranked[1:4] if score > 0]
           
           return RoleDetectionResult(
               primary_role=primary_role,
               confidence=min(1.0, confidence),  # Cap at 1.0
               secondary_roles=secondary_roles,
               keywords_matched=list(set(keywords))[:5],  # Top 5
               rationale=f"Matched {len(keywords)} keywords for {primary_role}"
           )
       
       def apply_role_to_prompt(self, prompt: str, role: str, roles_config: dict) -> str:
           """Prepend role prefix to prompt."""
           if role in roles_config and "prefix" in roles_config[role]:
               prefix = roles_config[role]["prefix"]
               return f"{prefix}\n\n{prompt}"
           return prompt
   ```

2. **`src/promptwise_v2/core/auto_role_applier.py`**
   ```python
   from .role_detector import RoleDetector, RoleDetectionResult
   from typing import Dict, Optional
   
   class AutoRoleApplier:
       """Apply auto-detected role + constraints to a request."""
       
       def __init__(self, role_detector: RoleDetector, roles_config: dict, config: dict):
           self.detector = role_detector
           self.roles_config = roles_config
           self.auto_role_enabled = config.get("auto_role_detection", {}).get("enabled", False)
           self.confidence_threshold = config.get("auto_role_detection", {}).get("confidence_threshold", 0.65)
       
       def apply(self, prompt: str, session_context: dict) -> Dict:
           """
           Detect role, apply prefix, and potentially apply constraints.
           
           Returns:
               {
                   "prompt": <modified prompt with prefix>,
                   "role": <detected or default role>,
                   "confidence": <0.0-1.0>,
                   "constraints": [<role-specific checks>],
                   "applied_features": [<list of applied features>]
               }
           """
           
           if not self.auto_role_enabled:
               return {"prompt": prompt, "role": "general", "confidence": 0, "constraints": []}
           
           # Detect role from prompt
           detection = self.detector.detect(prompt, context=session_context)
           
           if detection.confidence < self.confidence_threshold:
               # Fall back to general role
               return {
                   "prompt": prompt,
                   "role": "general",
                   "confidence": detection.confidence,
                   "constraints": [],
                   "rationale": f"Confidence {detection.confidence:.2f} below threshold {self.confidence_threshold}"
               }
           
           # Apply detected role
           modified_prompt = self.detector.apply_role_to_prompt(
               prompt, 
               detection.primary_role,
               self.roles_config
           )
           
           # Apply role-specific constraints
           constraints = self._get_constraints_for_role(detection.primary_role)
           
           return {
               "prompt": modified_prompt,
               "role": detection.primary_role,
               "confidence": detection.confidence,
               "secondary_roles": detection.secondary_roles,
               "keywords_matched": detection.keywords_matched,
               "constraints": constraints,
               "applied_features": ["role_prefix", "constraints"]
           }
       
       def _get_constraints_for_role(self, role: str) -> list:
           """Return role-specific workflow constraints."""
           
           constraints_map = {
               "developer": [
                   "prefer_code_blocks",
                   "include_imports",
                   "validate_syntax"
               ],
               "security": [
                   "flag_pii",
                   "check_compliance",
                   "mention_cve"
               ],
               "analyst": [
                   "include_sample_data",
                   "cite_sources",
                   "show_formulas"
               ],
               # ... etc
           }
           
           return constraints_map.get(role, [])
   ```

3. **`config/role_keywords.yaml`** (external config)
   ```yaml
   # Map of roles to detection keywords + patterns
   
   developer:
     keywords:
       - refactor
       - debug
       - code
       - function
       - api
       - library
       - bug
       - test
       - fix
       - import
       - module
       - class
       - def
     patterns:
       - "def\\s+\\w+"
       - "class\\s+\\w+"
       - "import\\s+"
       - "function\\s+"
     weight: 1.0
   
   analyst:
     keywords:
       - metrics
       - data
       - report
       - trend
       - aggregat
       - average
       - sum
       - count
       - compare
       - analyze
       - pivot
       - dashboard
     patterns:
       - "SELECT\\s+"
       - "aggregat"
       - "GROUP BY"
     weight: 0.9
   
   security:
     keywords:
       - auth
       - encrypt
       - vulnerability
       - compliance
       - gdpr
       - ccpa
       - pii
       - threat
       - risk
       - penetrat
       - exploit
       - vulnerability
     patterns:
       - "CVE-\\d+"
       - "OWASP"
       - "secure"
     weight: 1.0
   
   IT:
     keywords:
       - deploy
       - infra
       - scaling
       - failover
       - cloud
       - aws
       - kubernetes
       - docker
       - ci
       - cd
       - terraform
       - ansible
     patterns:
       - "kubectl"
       - "docker\\s+run"
       - "terraform\\s+"
     weight: 0.95
   
   # Add remaining 13 roles
   ```

**Tests to write:**

- `tests/v2/core/test_role_detector.py` — 50+ test cases
  ```python
  test_cases = [
      ("Refactor the payment module", "developer", 0.9),
      ("Analyze Q1 revenue by region", "analyst", 0.85),
      ("Deploy to us-east-1 with terraform", "IT", 0.95),
      ("GDPR audit on user data handling", "security", 0.88),
      ("Write a blog post about AI trends", "writer", 0.75),
      ("Unusual request with no role signals", "general", <0.6),  # Falls back
  ]
  ```

- `tests/v2/core/test_auto_role_applier.py` — Test prefix application, constraints

**Checklist:**
- [ ] Create `RoleDetector` with keyword + pattern matching
- [ ] Implement TF-IDF weighting (optional for v1; could be simple keyword counts)
- [ ] Create `AutoRoleApplier` to apply detected role
- [ ] Export role keywords to external `role_keywords.yaml` config file
- [ ] Write 50+ test cases covering all 17 roles
- [ ] Verify confidence threshold logic (0.65 default)
- [ ] Integration test: auto-detect role, apply prefix, verify prompt changes
- [ ] Document in README: "Auto-role detection enabled by default"

**Estimated effort:** 5 days (1 person)

---

### Task 1.3: Configuration & Documentation (4 days)

**Goal:** Finalize configs for multi-platform deployment; write integration guides.

**Files to update/create:**

1. **`config/promptwise_v2.yaml`** — Add auto-role settings
   ```yaml
   auto_role_detection:
     enabled: true
     confidence_threshold: 0.65
     apply_constraints: true
   
   platforms:
     mcp:
       enabled: true
     codex:
       enabled: false  # Set to true once API spec known
       api_key_env: "CODEX_API_KEY"
     gemini:
       enabled: true
       api_key_env: "GEMINI_API_KEY"
     antigravity:
       enabled: false  # Set to true once API spec known
       endpoint_env: "ANTIGRAVITY_ENDPOINT"
   ```

2. **`docs/integration/MULTI_PLATFORM.md`** — New document
   ```markdown
   # Multi-Platform Integration Guide
   
   PromptWise supports multiple deployment platforms:
   - **MCP** (Claude Code) — default
   - **Gemini** (Google AI API)
   - **Codex** (OpenAI Codex API) — pending pricing confirmation
   - **Antigravity CLI** — pending API spec
   
   ## For each platform:
   
   ### 1. Authentication
   
   **Gemini:**
   ```bash
   export GEMINI_API_KEY="your-google-api-key"
   ```
   
   **Codex:**
   ```bash
   export CODEX_API_KEY="your-codex-key"
   ```
   
   **Antigravity:**
   ```bash
   export ANTIGRAVITY_ENDPOINT="localhost:5000"
   ```
   
   ### 2. Run PromptWise
   
   **For Gemini:**
   ```bash
   python -m promptwise_v2.cli --platform gemini --model gemini-2.0-flash
   ```
   
   **For Codex:**
   ```bash
   python -m promptwise_v2.cli --platform codex
   ```
   
   **For Antigravity:**
   ```bash
   python -m promptwise_v2.cli --platform antigravity --endpoint $ANTIGRAVITY_ENDPOINT
   ```
   
   ### 3. Example: Route to best model
   
   ```python
   from promptwise_v2.adapters import create_adapter
   from promptwise_v2.transports import ToolRequest
   
   adapter = create_adapter("gemini", config={
       "gemini_api_key": os.getenv("GEMINI_API_KEY")
   })
   
   request = ToolRequest(
       tool_name="route_request",
       params={
           "text": "Analyze this 50-page legal document for compliance",
           "intent": "analysis",
           "stakes": "high",
           "budget_usd": 0.50
       },
       session_id="session-123"
   )
   
   response = await adapter.call_tool(request)
   print(response.result["recommended_model"])  # Might be: gemini-2.5-pro
   ```
   
   ## Troubleshooting
   
   | Error | Cause | Fix |
   |-------|-------|-----|
   | `AuthenticationError: Invalid API key` | API key not set or wrong | Check env var; verify key at provider console |
   | `ConnectionError: timeout` | Network issue or endpoint down | Check endpoint URL; test with curl |
   | `ValueError: Unknown platform` | Typo in platform name | Use one of: mcp, gemini, codex, antigravity |
   ```

3. **`docs/integration/CODEX_SETUP.md`** — Pending Codex API spec
   ```markdown
   # Codex Integration (PENDING API SPEC)
   
   **Status:** Awaiting Codex API documentation and pricing information.
   
   Once available, this guide will cover:
   - API authentication
   - Model selection (codex-4, codex-6, etc.)
   - Output format validation (code block extraction)
   - Cost tracking
   ```

4. **`docs/integration/ANTIGRAVITY_SETUP.md`** — Pending API spec
   ```markdown
   # Antigravity CLI Integration (PENDING API SPEC)
   
   **Status:** Awaiting Antigravity API documentation.
   
   Assumptions:
   - HTTP API at configurable endpoint, OR
   - Socket-based protocol (stdio), OR
   - Custom protocol (TBD)
   
   Once spec provided, this guide will cover:
   - Connection setup
   - Authentication
   - Request/response format
   - Error handling
   ```

5. **`README.md`** — Update supported platforms section
   ```markdown
   ## Supported Platforms
   
   | Platform | Status | Models | Cost Tracking |
   |----------|--------|--------|---|
   | **Claude Code (MCP)** | ✅ Production | Claude Haiku/Sonnet/Opus | Yes |
   | **Google Gemini** | ✅ Production | Flash/Pro/Pro-Thinking | Yes |
   | **OpenAI Codex** | 🟡 Coming Soon | codex-* | Pending spec |
   | **Antigravity CLI** | 🟡 Coming Soon | * | Pending spec |
   ```

6. **`.env.example`** — Template for developers
   ```bash
   # PromptWise Configuration
   
   # Gemini
   GEMINI_API_KEY=your-google-api-key
   
   # Codex (optional)
   CODEX_API_KEY=your-codex-key
   
   # Antigravity (optional)
   ANTIGRAVITY_ENDPOINT=http://localhost:5000
   
   # PromptWise
   PROMPTWISE_PLATFORM=mcp  # mcp, gemini, codex, antigravity
   PROMPTWISE_LOG_LEVEL=INFO
   ```

**Checklist:**
- [ ] Update `config/promptwise_v2.yaml` with auto-role + platform settings
- [ ] Create `docs/integration/MULTI_PLATFORM.md` (generic guide)
- [ ] Create `docs/integration/GEMINI.md` (working; deployment tested)
- [ ] Create `docs/integration/CODEX_SETUP.md` (template; pending API spec)
- [ ] Create `docs/integration/ANTIGRAVITY_SETUP.md` (template; pending API spec)
- [ ] Update main `README.md` with platform table
- [ ] Create `.env.example` template
- [ ] Link all guides from main README

**Estimated effort:** 4 days (1 person)

---

### PHASE 1 SUMMARY

| Task | Effort | Blocker? | Deliverable |
|------|--------|----------|------------|
| 1.1: Adapter Layer | 5 days | No | Transport abstraction (4 adapters) + tests |
| 1.2: Auto-Role Detection | 5 days | No | Role detector + applier + 50+ tests |
| 1.3: Config & Docs | 4 days | **Yes** | Codex/Antigravity API specs needed |
| **Total** | **14 days** | | Multi-platform foundation |

**Can parallelize:** Tasks 1.1 and 1.2 can run in parallel (2 engineers, both ready in week 2).

**Blockers:** Task 1.3 needs clarity on Codex tiers + Antigravity API spec (not blocking 1.1 and 1.2).

---

## PHASE 2: PLATFORM-SPECIFIC (Weeks 3-4)

### Task 2.1: Codex Adapter (5-7 days)

**Prerequisites:** Codex API spec + pricing tiers (BLOCKER)

**What to build:**
- [ ] Add Codex models to `pricing.yaml`
- [ ] Add Codex to `providers.yaml` (tiers, features, endpoints)
- [ ] Implement Codex-specific routing in `HTTPAdapter`
- [ ] Code-format output validator
- [ ] 15+ integration tests

---

### Task 2.2: Gemini Enhancements (3-4 days)

**Not blocking; nice-to-have:**
- [ ] Thinking-token tracking in stats (Pro-w-Thinking models)
- [ ] System instruction format validator (Gemini specific)
- [ ] Cache hit metrics dashboard
- [ ] 10+ new tests

---

### Task 2.3: Antigravity Adapter (5-7 days)

**Prerequisites:** Antigravity API spec (BLOCKER)

**What to build:**
- [ ] Auth integration (bearer token? OAuth?)
- [ ] Implement HTTP or CLI adapter depending on API type
- [ ] Request/response format mapping
- [ ] 15+ integration tests

---

## PHASE 3: OPTIMIZATION PROFILES (Week 5)

**What to build:**
- [ ] `config/optimization_profiles.yaml` schema
- [ ] `OptimizationProfileSelector` class
- [ ] Profile-aware compression/caching/batching rules
- [ ] Integration with `route_request` → auto-apply profile
- [ ] Metrics: track profile effectiveness
- [ ] 20+ tests

---

## PHASE 4: PHASE A TOOLS (Weeks 6+ — OPTIONAL, PARALLELIZABLE)

**10 design-complete tools (code from design doc):**

**Tier 1 (highest impact):**
- [ ] `compress_response` (output compression)
- [ ] `debug_gate` (systematic debugging enforcement)
- [ ] `tdd_gate` (TDD iron-law gate)
- [ ] `verification_gate` (completion verification)
- [ ] `agent_roles` (builder/investigator/reviewer templates)

**Tier 2:**
- [ ] `dispatch_parallel` (concurrent subagent dispatch)
- [ ] `review_pipeline` (2-stage code review)
- [ ] `triage_defect` (defect classification)
- [ ] `test_strategy` (test matrix generator)

**Tier 3:**
- [ ] `plan_feature` (feature planning chain)

**Effort per tool:** 2-3 days (can be done in parallel; 2 people finish in 2-3 weeks)

---

## DEPENDENCIES & BLOCKERS

### Must Resolve Before Starting Phase 2

| Blocker | Owner | Timeline | Impact |
|---------|-------|----------|--------|
| **Codex API spec + pricing tiers** | Codex team | TBD | Blocks Task 2.1 (1 week delay per week slipped) |
| **Antigravity API documentation** | Antigravity team | TBD | Blocks Task 2.3 (1 week delay per week slipped) |

### Can Work Around

| Issue | Workaround |
|-------|-----------|
| Antigravity API unknown | Build CLI adapter with stdio protocol; config-driven endpoint; easy to pivot once spec known |
| Codex pricing unstable | Pin pricing.yaml to specific date; alert user if pricing >30 days stale |

---

## SUCCESS CRITERIA

### By End of Phase 1 (Week 2)

- [ ] All 4 transport adapters implemented (MCP, HTTP, CLI, factory)
- [ ] Auto-role detection works for 17 roles with 85%+ accuracy
- [ ] 70+ new tests pass (transport + role detection)
- [ ] README documents 4 platforms (MCP, Gemini, Codex*, Antigravity*)
- [ ] All team members can run PromptWise on Gemini API directly

### By End of Phase 2 (Week 4)

- [ ] Codex adapter complete (pending API spec; mock tests pass)
- [ ] Antigravity adapter complete (pending API spec; mock tests pass)
- [ ] Gemini enhancements merged
- [ ] 30+ new integration tests pass

### By End of Phase 3 (Week 5)

- [ ] Optimization profiles defined + integrated
- [ ] Profile effectiveness tracked (cost saved per profile)
- [ ] Documentation: "Profile selection by model" example

### By End of Phase 4 (Week 6+)

- [ ] 10 Phase A tools implemented
- [ ] 50+ tests for new tools
- [ ] All agentic features (gates, dispatch, review) functional

---

## RECOMMENDED TEAM STRUCTURE

### Week 1-2 (Phase 1)

**2 engineers (parallel):**
- Engineer A: Transport adapters (Task 1.1)
- Engineer B: Auto-role detection (Task 1.2)
- Engineer C (optional): Config/docs (Task 1.3)

### Week 3-4 (Phase 2)

**2 engineers (parallel):**
- Engineer A: Codex adapter (Task 2.1)
- Engineer B: Antigravity adapter (Task 2.3)
- Overlap: Gemini enhancements (Task 2.2) — done in 3-4 days, not time-critical

### Week 5 (Phase 3)

**1 engineer:**
- Optimization profiles
- Runs in parallel with Phase A tools if team scales

### Week 6+ (Phase 4)

**2 engineers (parallel):**
- Engineer A: Tier 1 tools (compress_response, gates)
- Engineer B: Tier 2 tools (dispatch, review, triage)
- Engineer C (optional): Tier 3 tool (plan_feature) + tests

---

## ROLLOUT PLAN

### Beta (End of Phase 1)

- Release v2.1.0 (transport adapters + auto-role)
- Available: MCP (production), Gemini (production), Codex (alpha*), Antigravity (alpha*)
- *alpha = with mock tests only; pending real API access

### GA (End of Phase 2)

- Release v2.2.0 (full Codex + Antigravity support)
- All platforms production-ready
- Full integration tests passing on real APIs

### Enhanced (End of Phase 3)

- Release v2.3.0 (optimization profiles)
- Auto-profile selection per model
- Metrics dashboard

### Agentic (End of Phase 4+)

- Release v2.4.0 (Phase A tools)
- Dev workflow enforcement (gates, debug, TDD)
- Parallel dispatch and code review automation

---

## APPENDIX: Testing Strategy

### Unit Tests

- Role detector: 50+ cases (intent, stakes, context variations)
- Transport adapters: 20+ cases (factory, call routing, error handling)
- Config validators: 30+ cases (YAML parsing, schema validation)

### Integration Tests (Mocks)

- Mock HTTP endpoints for Codex, Gemini, Antigravity
- Test end-to-end flow: tool call → adapter → provider → response
- Test failover: one provider unavailable → route to another

### Integration Tests (Real APIs)

- Staging accounts for Gemini, Codex, Antigravity (if available)
- Run 10 real prompts per platform
- Verify cost calculation matches actual API response
- Verify auto-role detection on real requests

### Load Tests (Optional)

- 100 concurrent requests per adapter
- Measure latency, error rate, resource usage

---

## QUICK REFERENCE: File Checklist

### Phase 1 New Files

```
src/promptwise_v2/
  └── transports/
      ├── __init__.py              (TransportAdapter ABC)
      ├── mcp_adapter.py
      ├── http_adapter.py
      └── cli_adapter.py
  ├── adapters/
      └── __init__.py              (create_adapter factory)
  └── core/
      ├── role_detector.py
      └── auto_role_applier.py

config/
  ├── promptwise_v2.yaml           (updated: auto-role + platforms)
  └── role_keywords.yaml           (new: keywords per role)

docs/integration/
  ├── MULTI_PLATFORM.md
  ├── GEMINI.md
  ├── CODEX_SETUP.md               (template, pending spec)
  └── ANTIGRAVITY_SETUP.md         (template, pending spec)

tests/v2/
  ├── transports/
  │   ├── test_mcp_adapter.py
  │   ├── test_http_adapter.py
  │   └── test_cli_adapter.py
  ├── core/
  │   ├── test_role_detector.py
  │   └── test_auto_role_applier.py
  └── test_adapter_factory.py

.env.example                       (new: env template)
```

### Phase 2 New Files

```
config/
  └── optimization_profiles.yaml   (new)

src/promptwise_v2/
  └── core/
      ├── profile_selector.py      (new)
      └── codex_output_validator.py (new)

docs/integration/
  ├── CODEX.md                     (filled from template)
  └── ANTIGRAVITY.md               (filled from template)

tests/v2/
  └── core/
      ├── test_codex_validator.py
      └── test_profile_selector.py
```

---

**Prepared by:** Code Review Agent  
**Date:** 2026-06-07  
**Status:** Ready for implementation kickoff
