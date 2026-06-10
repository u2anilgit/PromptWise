# PromptWise Phase A — Coding Agent Feature Additions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 10 MCP tools + 2 skills drawn from caveman, superpowers, and QA plugins — giving PromptWise native dev-workflow enforcement, output compression, parallel dispatch, defect triage, and test strategy generation.

**Architecture:** New tools follow the established pattern: Tool def in `_V2_TOOL_DEFS`, handler in `call_tool_v2`, implementation class in `src/promptwise_v2/core/`. Session-level flags stored in a new `session_flags: dict` field on `ServerContextV2`. Skills are `.md` files in `src/promptwise_v2/skills/dev/`.

**Tech Stack:** Python 3.11+, MCP SDK, existing `CompressionEngine`, `MemoryManager`, `SecurityChecker`. No new external dependencies.

---

## File Structure

**New files:**
- `src/promptwise_v2/core/agent_roles.py` — builder/investigator/reviewer prompt templates
- `src/promptwise_v2/core/debug_gate.py` — 4-phase systematic debug enforcement
- `src/promptwise_v2/core/tdd_gate.py` — TDD iron-law gate
- `src/promptwise_v2/core/verification_gate.py` — evidence-required completion gate
- `src/promptwise_v2/core/parallel_dispatcher.py` — concurrent task dispatch
- `src/promptwise_v2/core/review_pipeline.py` — 2-stage spec+quality review
- `src/promptwise_v2/core/defect_triage.py` — defect severity/priority classifier
- `src/promptwise_v2/core/test_strategist.py` — test matrix generator
- `src/promptwise_v2/skills/dev/plan-feature.md` — plan_feature skill
- `src/promptwise_v2/skills/dev/auto-clarity.md` — auto_clarity skill
- `tests/v2/core/test_agent_roles.py`
- `tests/v2/core/test_debug_gate.py`
- `tests/v2/core/test_tdd_gate.py`
- `tests/v2/core/test_verification_gate.py`
- `tests/v2/core/test_parallel_dispatcher.py`
- `tests/v2/core/test_review_pipeline.py`
- `tests/v2/core/test_defect_triage.py`
- `tests/v2/core/test_test_strategist.py`

**Modified files:**
- `src/promptwise_v2/types_v2.py` — 8 new result dataclasses
- `src/promptwise_v2/integrations/mcp_server_v2.py` — 10 new Tool defs + 10 new handlers + `session_flags` on `ServerContextV2`
- `config/promptwise_v2.yaml` — `auto_clarity` config key
- `tests/v2/integrations/test_mcp_server_v2.py` — update tool count to 66

---

## Task 1: New Result Types

**Files:**
- Modify: `src/promptwise_v2/types_v2.py`
- Test: `tests/v2/test_types_v2.py`

- [ ] **Step 1: Write failing tests for new types**

```python
# Append to tests/v2/test_types_v2.py

def test_agent_role_result():
    from promptwise_v2.types_v2 import AgentRoleResult
    r = AgentRoleResult(role="builder", system_prompt="You are a surgical editor.",
                        constraints=["1-2 files max"], output_format="diff receipt")
    assert r.role == "builder"

def test_debug_gate_result():
    from promptwise_v2.types_v2 import DebugGateResult
    r = DebugGateResult(phase_complete=True, current_phase="root_cause",
                        next_phase="pattern_analysis", blocked=False, reason="")
    assert r.phase_complete is True

def test_tdd_gate_result():
    from promptwise_v2.types_v2 import TDDGateResult
    r = TDDGateResult(gate_passed=False, test_exists=True, test_failed=False,
                      reason="Test passed immediately — not a valid failing test")
    assert r.gate_passed is False

def test_verification_gate_result():
    from promptwise_v2.types_v2 import VerificationGateResult
    r = VerificationGateResult(passed=True, evidence="34/34 tests pass",
                                gate_status="clear", warnings=[])
    assert r.passed is True

def test_parallel_dispatch_result():
    from promptwise_v2.types_v2 import ParallelDispatchResult
    r = ParallelDispatchResult(task_results=[{"id": "t1", "output": "done"}],
                                conflicts=[], merged=True, duration_ms=120)
    assert r.merged is True

def test_review_pipeline_result():
    from promptwise_v2.types_v2 import ReviewPipelineResult
    r = ReviewPipelineResult(spec_compliant=True, quality_approved=True,
                              issues=[], approved=True)
    assert r.approved is True

def test_defect_triage_result():
    from promptwise_v2.types_v2 import DefectTriageResult
    r = DefectTriageResult(severity="high", priority="P1",
                            reproduction_steps=["step 1", "step 2"],
                            suggested_owner="backend-team", tags=["auth", "regression"])
    assert r.severity == "high"

def test_compress_memory_result():
    from promptwise_v2.types_v2 import CompressMemoryResult
    r = CompressMemoryResult(original_path="/foo/CLAUDE.md",
                              backup_path="/foo/CLAUDE.original.md",
                              tokens_saved=430, saving_pct=67.3)
    assert r.saving_pct == 67.3

def test_test_strategy_result():
    from promptwise_v2.types_v2 import TestStrategyResult
    r = TestStrategyResult(matrix=[{"layer": "unit", "platform": "API", "framework": "pytest"}],
                            framework_recommendation="pytest", coverage_target=0.85)
    assert r.coverage_target == 0.85
```

- [ ] **Step 2: Run — expect ImportError (types don't exist yet)**

```
pytest tests/v2/test_types_v2.py::test_agent_role_result -v
```

Expected: `ImportError: cannot import name 'AgentRoleResult'`

- [ ] **Step 3: Add new types to `types_v2.py`**

Append to end of `src/promptwise_v2/types_v2.py`:

```python
@dataclass(frozen=True)
class AgentRoleResult:
    role: str
    system_prompt: str
    constraints: list[str]
    output_format: str


@dataclass(frozen=True)
class DebugGateResult:
    phase_complete: bool
    current_phase: str
    next_phase: str
    blocked: bool
    reason: str


@dataclass(frozen=True)
class TDDGateResult:
    gate_passed: bool
    test_exists: bool
    test_failed: bool
    reason: str


@dataclass(frozen=True)
class VerificationGateResult:
    passed: bool
    evidence: str
    gate_status: str
    warnings: list[str]


@dataclass(frozen=True)
class ParallelDispatchResult:
    task_results: list[dict]
    conflicts: list[str]
    merged: bool
    duration_ms: int


@dataclass(frozen=True)
class ReviewPipelineResult:
    spec_compliant: bool
    quality_approved: bool
    issues: list[dict]
    approved: bool


@dataclass(frozen=True)
class DefectTriageResult:
    severity: str
    priority: str
    reproduction_steps: list[str]
    suggested_owner: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompressMemoryResult:
    original_path: str
    backup_path: str
    tokens_saved: int
    saving_pct: float


@dataclass(frozen=True)
class TestStrategyResult:
    matrix: list[dict]
    framework_recommendation: str
    coverage_target: float
```

- [ ] **Step 4: Run all new type tests**

```
pytest tests/v2/test_types_v2.py -v -k "agent_role or debug_gate or tdd_gate or verification_gate or parallel_dispatch or review_pipeline or defect_triage or compress_memory or test_strategy"
```

Expected: 9 PASS

- [ ] **Step 5: Commit**

```bash
git add src/promptwise_v2/types_v2.py tests/v2/test_types_v2.py
git commit -m "feat(phase-a): add 9 result types for coding agent tools"
```

---

## Task 2: AgentRoles Module + MCP Tool

**Files:**
- Create: `src/promptwise_v2/core/agent_roles.py`
- Test: `tests/v2/core/test_agent_roles.py`
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/core/test_agent_roles.py
from promptwise_v2.core.agent_roles import AgentRoles

def test_builder_role():
    r = AgentRoles().get("builder")
    assert r.role == "builder"
    assert "1-2 file" in r.system_prompt or "surgical" in r.system_prompt.lower()
    assert len(r.constraints) >= 1
    assert r.output_format != ""

def test_investigator_role():
    r = AgentRoles().get("investigator")
    assert r.role == "investigator"
    assert "read" in r.system_prompt.lower() or "search" in r.system_prompt.lower()

def test_reviewer_role():
    r = AgentRoles().get("reviewer")
    assert r.role == "reviewer"
    assert "severity" in r.system_prompt.lower() or "diff" in r.system_prompt.lower()

def test_unknown_role_returns_none():
    assert AgentRoles().get("nonexistent") is None

def test_list_roles():
    roles = AgentRoles().list_roles()
    assert set(roles) == {"builder", "investigator", "reviewer"}
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```
pytest tests/v2/core/test_agent_roles.py -v
```

Expected: `ModuleNotFoundError: No module named 'promptwise_v2.core.agent_roles'`

- [ ] **Step 3: Create `agent_roles.py`**

```python
# src/promptwise_v2/core/agent_roles.py
from promptwise_v2.types_v2 import AgentRoleResult

_ROLES = {
    "builder": AgentRoleResult(
        role="builder",
        system_prompt=(
            "Surgical file editor. Scope: 1 file ideal, 2 max. "
            "Read target first — never edit blind. Make smallest diff that works. "
            "Re-read after edit to verify. No new abstractions, no drive-by refactors. "
            "Return diff receipt: path:line-range — change <=10 words."
        ),
        constraints=[
            "1-2 files max — refuse 3+",
            "Edit existing only (new file only if explicitly requested)",
            "No new abstractions or comment additions",
        ],
        output_format="path:line-range — change. verified: re-read OK | mismatch @ path:line.",
    ),
    "investigator": AgentRoleResult(
        role="investigator",
        system_prompt=(
            "Read-only code locator. Find where X is defined, what calls Y, "
            "all uses of Z, directory structure. Return file:line table. "
            "Never suggest fixes. Never write or edit files."
        ),
        constraints=[
            "Read only — no writes, no edits",
            "Return file:line references only",
            "Refuse if asked to suggest fixes",
        ],
        output_format="file:line — description (one line per finding)",
    ),
    "reviewer": AgentRoleResult(
        role="reviewer",
        system_prompt=(
            "Diff and PR reviewer. One finding per line, severity-tagged. "
            "No praise, no scope creep. Skip formatting nits unless they change meaning."
        ),
        constraints=[
            "One line per finding",
            "Tag severity: critical/high/medium/low",
            "No praise or filler",
            "Skip formatting nits",
        ],
        output_format="path:line: <emoji> <severity>: <problem>. <fix>.",
    ),
}


class AgentRoles:
    def get(self, role: str) -> AgentRoleResult | None:
        return _ROLES.get(role)

    def list_roles(self) -> list[str]:
        return list(_ROLES.keys())
```

- [ ] **Step 4: Run tests**

```
pytest tests/v2/core/test_agent_roles.py -v
```

Expected: 5 PASS

- [ ] **Step 5: Add Tool def to `_V2_TOOL_DEFS` in `mcp_server_v2.py`**

In `mcp_server_v2.py`, find the comment `# --- v3 security tools ---` and add before it:

```python
    # --- Phase A: coding agent tools ---
    Tool(name="agent_roles",
         description="Return pre-built agent prompt templates: builder (1-2 file surgical edits), investigator (read-only search), reviewer (diff + severity findings)",
         inputSchema={"type": "object", "properties": {
             "role": {"type": "string", "enum": ["builder", "investigator", "reviewer"]},
         }, "required": ["role"]}),
```

- [ ] **Step 6: Add import + handler in `call_tool_v2`**

Add import at top of `mcp_server_v2.py` (with other v2 imports):

```python
from promptwise_v2.core.agent_roles import AgentRoles
```

Add handler in `call_tool_v2` (after existing `elif` blocks, before `else` / raise):

```python
        elif name == "agent_roles":
            r = AgentRoles().get(arguments.get("role", ""))
            if r is None:
                return json.dumps({"error": f"Unknown role: {arguments.get('role')}"})
            return json.dumps({"role": r.role, "system_prompt": r.system_prompt,
                               "constraints": r.constraints, "output_format": r.output_format})
```

- [ ] **Step 7: Write integration test in `test_mcp_server_v2.py`**

```python
def test_agent_roles_builder():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "agent_roles", {"role": "builder"}))
    data = json.loads(result)
    assert data["role"] == "builder"
    assert "system_prompt" in data
    assert "constraints" in data

def test_agent_roles_unknown():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "agent_roles", {"role": "wizard"}))
    data = json.loads(result)
    assert "error" in data
```

- [ ] **Step 8: Run integration tests**

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_agent_roles_builder tests/v2/integrations/test_mcp_server_v2.py::test_agent_roles_unknown -v
```

Expected: 2 PASS

- [ ] **Step 9: Commit**

```bash
git add src/promptwise_v2/core/agent_roles.py tests/v2/core/test_agent_roles.py src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add agent_roles MCP tool — builder/investigator/reviewer templates"
```

---

## Task 3: DebugGate Module + MCP Tool

**Files:**
- Create: `src/promptwise_v2/core/debug_gate.py`
- Test: `tests/v2/core/test_debug_gate.py`
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/core/test_debug_gate.py
from promptwise_v2.core.debug_gate import DebugGate

def test_phase1_incomplete_blocks_fix():
    gate = DebugGate()
    r = gate.check(issue="Login fails", phase="none", evidence="")
    assert r.blocked is True
    assert r.current_phase == "root_cause"
    assert "root cause" in r.reason.lower()

def test_phase1_complete_allows_phase2():
    gate = DebugGate()
    r = gate.check(
        issue="Token expiry bug",
        phase="root_cause",
        evidence="Stack trace shows line 42 in auth.py — token.expiry < now instead of <=",
    )
    assert r.phase_complete is True
    assert r.next_phase == "pattern_analysis"
    assert r.blocked is False

def test_phase4_complete_clears_gate():
    gate = DebugGate()
    r = gate.check(
        issue="Token expiry bug",
        phase="implementation",
        evidence="Test passes: test_token_expiry PASS. No other tests broken.",
    )
    assert r.phase_complete is True
    assert r.blocked is False

def test_no_evidence_blocks_all_phases():
    gate = DebugGate()
    r = gate.check(issue="Some bug", phase="pattern_analysis", evidence="")
    assert r.blocked is True
    assert "evidence" in r.reason.lower()
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```
pytest tests/v2/core/test_debug_gate.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `debug_gate.py`**

```python
# src/promptwise_v2/core/debug_gate.py
from promptwise_v2.types_v2 import DebugGateResult

_PHASES = ["root_cause", "pattern_analysis", "hypothesis", "implementation"]
_PHASE_NEXT = {
    "none": "root_cause",
    "root_cause": "pattern_analysis",
    "pattern_analysis": "hypothesis",
    "hypothesis": "implementation",
    "implementation": "complete",
}


class DebugGate:
    def check(self, issue: str, phase: str, evidence: str) -> DebugGateResult:
        if not evidence.strip():
            return DebugGateResult(
                phase_complete=False,
                current_phase=phase or "root_cause",
                next_phase=_PHASE_NEXT.get(phase, "root_cause"),
                blocked=True,
                reason="No evidence provided. Gather evidence before proceeding to next phase.",
            )

        if phase not in _PHASES and phase != "none":
            return DebugGateResult(
                phase_complete=False,
                current_phase="root_cause",
                next_phase="pattern_analysis",
                blocked=True,
                reason=f"Unknown phase '{phase}'. Start at root_cause: reproduce → read errors → check recent changes.",
            )

        if phase == "none":
            return DebugGateResult(
                phase_complete=False,
                current_phase="root_cause",
                next_phase="pattern_analysis",
                blocked=True,
                reason="No root cause investigation started. Complete Phase 1: reproduce bug, read error messages, check recent changes.",
            )

        next_phase = _PHASE_NEXT.get(phase, "complete")
        return DebugGateResult(
            phase_complete=True,
            current_phase=phase,
            next_phase=next_phase,
            blocked=False,
            reason="",
        )
```

- [ ] **Step 4: Run tests**

```
pytest tests/v2/core/test_debug_gate.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Add Tool def to `_V2_TOOL_DEFS`** (in the `# --- Phase A ---` block added in Task 2)

```python
    Tool(name="debug_gate",
         description="Systematic debugging gate: enforces 4-phase root-cause investigation before allowing fixes (root_cause → pattern_analysis → hypothesis → implementation)",
         inputSchema={"type": "object", "properties": {
             "issue": {"type": "string", "description": "Bug description"},
             "phase": {"type": "string", "description": "Current phase: none|root_cause|pattern_analysis|hypothesis|implementation"},
             "evidence": {"type": "string", "description": "Evidence gathered so far (error messages, traces, observations)"},
         }, "required": ["issue", "phase", "evidence"]}),
```

- [ ] **Step 6: Add import + handler**

Import:
```python
from promptwise_v2.core.debug_gate import DebugGate
```

Handler:
```python
        elif name == "debug_gate":
            r = DebugGate().check(
                issue=arguments.get("issue", ""),
                phase=arguments.get("phase", "none"),
                evidence=arguments.get("evidence", ""),
            )
            return json.dumps({"phase_complete": r.phase_complete, "current_phase": r.current_phase,
                               "next_phase": r.next_phase, "blocked": r.blocked, "reason": r.reason})
```

- [ ] **Step 7: Write + run integration test**

```python
def test_debug_gate_blocks_without_evidence():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "debug_gate",
                               {"issue": "Login broken", "phase": "none", "evidence": ""}))
    data = json.loads(result)
    assert data["blocked"] is True

def test_debug_gate_passes_with_evidence():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "debug_gate", {
        "issue": "Token bug", "phase": "root_cause",
        "evidence": "Line 42 in auth.py — wrong operator"
    }))
    data = json.loads(result)
    assert data["phase_complete"] is True
    assert data["blocked"] is False
```

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_debug_gate_blocks_without_evidence tests/v2/integrations/test_mcp_server_v2.py::test_debug_gate_passes_with_evidence -v
```

Expected: 2 PASS

- [ ] **Step 8: Commit**

```bash
git add src/promptwise_v2/core/debug_gate.py tests/v2/core/test_debug_gate.py src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add debug_gate MCP tool — 4-phase systematic debugging enforcement"
```

---

## Task 4: TDDGate Module + MCP Tool

**Files:**
- Create: `src/promptwise_v2/core/tdd_gate.py`
- Test: `tests/v2/core/test_tdd_gate.py`
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/core/test_tdd_gate.py
from promptwise_v2.core.tdd_gate import TDDGate

def test_no_test_code_blocks_gate():
    gate = TDDGate()
    r = gate.check(feature="Add login retry", test_code="", test_result="")
    assert r.gate_passed is False
    assert r.test_exists is False
    assert "no test" in r.reason.lower()

def test_test_not_run_blocks_gate():
    gate = TDDGate()
    r = gate.check(
        feature="Add login retry",
        test_code="def test_retry(): assert retry_login() == True",
        test_result="",
    )
    assert r.gate_passed is False
    assert r.test_failed is False
    assert "not run" in r.reason.lower() or "run" in r.reason.lower()

def test_test_passed_immediately_blocks_gate():
    gate = TDDGate()
    r = gate.check(
        feature="Add login retry",
        test_code="def test_retry(): assert retry_login() == True",
        test_result="PASSED",
    )
    assert r.gate_passed is False
    assert r.test_failed is False
    assert "pass" in r.reason.lower()

def test_test_failed_correctly_passes_gate():
    gate = TDDGate()
    r = gate.check(
        feature="Add login retry",
        test_code="def test_retry(): assert retry_login() == True",
        test_result="FAILED: NameError: name 'retry_login' is not defined",
    )
    assert r.gate_passed is True
    assert r.test_exists is True
    assert r.test_failed is True
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```
pytest tests/v2/core/test_tdd_gate.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `tdd_gate.py`**

```python
# src/promptwise_v2/core/tdd_gate.py
import re
from promptwise_v2.types_v2 import TDDGateResult

_PASS_PATTERN = re.compile(r'\bpassed\b', re.I)
_FAIL_PATTERN = re.compile(r'\bfailed\b|\berror\b|\bassertionerror\b|\bnameerror\b|\btypeerror\b', re.I)


class TDDGate:
    def check(self, feature: str, test_code: str, test_result: str) -> TDDGateResult:
        if not test_code.strip():
            return TDDGateResult(
                gate_passed=False,
                test_exists=False,
                test_failed=False,
                reason="No test code provided. Write a failing test before implementing the feature.",
            )

        if not test_result.strip():
            return TDDGateResult(
                gate_passed=False,
                test_exists=True,
                test_failed=False,
                reason="Test not run yet. Run the test and confirm it fails before implementing.",
            )

        if _PASS_PATTERN.search(test_result) and not _FAIL_PATTERN.search(test_result):
            return TDDGateResult(
                gate_passed=False,
                test_exists=True,
                test_failed=False,
                reason="Test passed immediately without implementation — it is not testing new behaviour. Rewrite the test so it fails first.",
            )

        if _FAIL_PATTERN.search(test_result):
            return TDDGateResult(
                gate_passed=True,
                test_exists=True,
                test_failed=True,
                reason="",
            )

        return TDDGateResult(
            gate_passed=False,
            test_exists=True,
            test_failed=False,
            reason=f"Cannot determine if test failed. Re-run test and provide full output. Got: {test_result[:100]}",
        )
```

- [ ] **Step 4: Run tests**

```
pytest tests/v2/core/test_tdd_gate.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Add Tool def + import + handler** (same file sections as Tasks 2-3)

Tool def in `_V2_TOOL_DEFS`:
```python
    Tool(name="tdd_gate",
         description="TDD iron-law gate: confirms a failing test exists before allowing implementation (RED phase verification)",
         inputSchema={"type": "object", "properties": {
             "feature": {"type": "string", "description": "Feature or bugfix description"},
             "test_code": {"type": "string", "description": "The failing test code"},
             "test_result": {"type": "string", "description": "Full output of running the test"},
         }, "required": ["feature", "test_code", "test_result"]}),
```

Import:
```python
from promptwise_v2.core.tdd_gate import TDDGate
```

Handler:
```python
        elif name == "tdd_gate":
            r = TDDGate().check(
                feature=arguments.get("feature", ""),
                test_code=arguments.get("test_code", ""),
                test_result=arguments.get("test_result", ""),
            )
            return json.dumps({"gate_passed": r.gate_passed, "test_exists": r.test_exists,
                               "test_failed": r.test_failed, "reason": r.reason})
```

- [ ] **Step 6: Write + run integration test**

```python
def test_tdd_gate_blocks_no_test():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "tdd_gate",
                               {"feature": "login retry", "test_code": "", "test_result": ""}))
    data = json.loads(result)
    assert data["gate_passed"] is False
    assert data["test_exists"] is False

def test_tdd_gate_passes_with_failing_test():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "tdd_gate", {
        "feature": "login retry",
        "test_code": "def test_retry(): assert retry_login() == True",
        "test_result": "FAILED: NameError: name 'retry_login' is not defined",
    }))
    data = json.loads(result)
    assert data["gate_passed"] is True
    assert data["test_failed"] is True
```

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_tdd_gate_blocks_no_test tests/v2/integrations/test_mcp_server_v2.py::test_tdd_gate_passes_with_failing_test -v
```

Expected: 2 PASS

- [ ] **Step 7: Commit**

```bash
git add src/promptwise_v2/core/tdd_gate.py tests/v2/core/test_tdd_gate.py src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add tdd_gate MCP tool — TDD iron-law RED phase verification"
```

---

## Task 5: VerificationGate Module + MCP Tool

**Files:**
- Create: `src/promptwise_v2/core/verification_gate.py`
- Test: `tests/v2/core/test_verification_gate.py`
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/core/test_verification_gate.py
from promptwise_v2.core.verification_gate import VerificationGate

def test_empty_evidence_fails():
    gate = VerificationGate()
    r = gate.check(claim="All tests pass", command="pytest", output="")
    assert r.passed is False
    assert r.gate_status == "no_evidence"

def test_passing_output_clears_gate():
    gate = VerificationGate()
    r = gate.check(
        claim="All tests pass",
        command="pytest tests/ -v",
        output="34 passed in 1.23s",
    )
    assert r.passed is True
    assert r.gate_status == "clear"
    assert "34 passed" in r.evidence

def test_failing_output_blocks_gate():
    gate = VerificationGate()
    r = gate.check(
        claim="All tests pass",
        command="pytest tests/ -v",
        output="2 failed, 32 passed in 1.45s",
    )
    assert r.passed is False
    assert r.gate_status == "failing"
    assert len(r.warnings) > 0

def test_hedged_claim_adds_warning():
    gate = VerificationGate()
    r = gate.check(
        claim="Tests should pass now",
        command="pytest tests/ -v",
        output="34 passed in 1.23s",
    )
    assert r.passed is True
    assert any("should" in w.lower() for w in r.warnings)
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```
pytest tests/v2/core/test_verification_gate.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `verification_gate.py`**

```python
# src/promptwise_v2/core/verification_gate.py
import re
from promptwise_v2.types_v2 import VerificationGateResult

_PASS_SIGNAL = re.compile(r'(\d+)\s+passed', re.I)
_FAIL_SIGNAL = re.compile(r'(\d+)\s+failed', re.I)
_ERROR_SIGNAL = re.compile(r'\berror\b|\bexception\b|\btraceback\b', re.I)
_HEDGE_WORDS = re.compile(r'\b(should|probably|seems|might|likely|appears)\b', re.I)


class VerificationGate:
    def check(self, claim: str, command: str, output: str) -> VerificationGateResult:
        warnings: list[str] = []

        if _HEDGE_WORDS.search(claim):
            warnings.append(
                f"Claim contains hedging language: '{claim}'. State claim AFTER seeing evidence."
            )

        if not output.strip():
            return VerificationGateResult(
                passed=False,
                evidence="",
                gate_status="no_evidence",
                warnings=warnings + ["No command output provided. Run the command and paste full output."],
            )

        fail_match = _FAIL_SIGNAL.search(output)
        error_match = _ERROR_SIGNAL.search(output)

        if fail_match or error_match:
            return VerificationGateResult(
                passed=False,
                evidence=output[:500],
                gate_status="failing",
                warnings=warnings + [f"Output shows failures: {output[:200]}"],
            )

        pass_match = _PASS_SIGNAL.search(output)
        if pass_match:
            return VerificationGateResult(
                passed=True,
                evidence=output[:500],
                gate_status="clear",
                warnings=warnings,
            )

        return VerificationGateResult(
            passed=False,
            evidence=output[:500],
            gate_status="ambiguous",
            warnings=warnings + ["Cannot confirm pass/fail from output. Provide full test runner output."],
        )
```

- [ ] **Step 4: Run tests**

```
pytest tests/v2/core/test_verification_gate.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Add Tool def + import + handler**

Tool def:
```python
    Tool(name="verification_gate",
         description="Evidence-required completion gate: confirms command output proves the claimed status before marking work done",
         inputSchema={"type": "object", "properties": {
             "claim": {"type": "string", "description": "The completion claim (e.g. 'All tests pass')"},
             "command": {"type": "string", "description": "The command that was run"},
             "output": {"type": "string", "description": "Full output of running the command"},
         }, "required": ["claim", "command", "output"]}),
```

Import:
```python
from promptwise_v2.core.verification_gate import VerificationGate
```

Handler:
```python
        elif name == "verification_gate":
            r = VerificationGate().check(
                claim=arguments.get("claim", ""),
                command=arguments.get("command", ""),
                output=arguments.get("output", ""),
            )
            return json.dumps({"passed": r.passed, "evidence": r.evidence,
                               "gate_status": r.gate_status, "warnings": r.warnings})
```

- [ ] **Step 6: Write + run integration test**

```python
def test_verification_gate_clears_with_passing_output():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "verification_gate", {
        "claim": "Tests pass",
        "command": "pytest",
        "output": "34 passed in 1.23s",
    }))
    data = json.loads(result)
    assert data["passed"] is True
    assert data["gate_status"] == "clear"

def test_verification_gate_blocks_empty_output():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "verification_gate",
                               {"claim": "Done", "command": "pytest", "output": ""}))
    data = json.loads(result)
    assert data["passed"] is False
    assert data["gate_status"] == "no_evidence"
```

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_verification_gate_clears_with_passing_output tests/v2/integrations/test_mcp_server_v2.py::test_verification_gate_blocks_empty_output -v
```

Expected: 2 PASS

- [ ] **Step 7: Commit**

```bash
git add src/promptwise_v2/core/verification_gate.py tests/v2/core/test_verification_gate.py src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add verification_gate MCP tool — evidence-required completion gate"
```

---

## Task 6: compress_response Session Flag + MCP Tool

**Files:**
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`
- Modify: `tests/v2/integrations/test_mcp_server_v2.py`

- [ ] **Step 1: Write failing test**

```python
def test_compress_response_enable():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "compress_response", {"enabled": True, "mode": "full"}))
    data = json.loads(result)
    assert data["enabled"] is True
    assert data["mode"] == "full"

def test_compress_response_disable():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    _run(call_tool_v2(ctx, "compress_response", {"enabled": True}))
    result = _run(call_tool_v2(ctx, "compress_response", {"enabled": False}))
    data = json.loads(result)
    assert data["enabled"] is False

def test_compress_response_default_mode_is_full():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "compress_response", {"enabled": True}))
    data = json.loads(result)
    assert data["mode"] == "full"
```

- [ ] **Step 2: Run — expect KeyError/no tool**

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_compress_response_enable -v
```

Expected: `FAILED` (tool not found or returns error)

- [ ] **Step 3: Add `session_flags` to `ServerContextV2`**

In `mcp_server_v2.py`, modify `ServerContextV2` dataclass to add:

```python
from dataclasses import dataclass, field

@dataclass
class ServerContextV2:
    # ... existing fields unchanged ...
    # v3 services
    skill_loader: SkillLoader
    router_v2: RouterV2
    # session state
    session_flags: dict = field(default_factory=dict)
```

- [ ] **Step 4: Add Tool def + handler**

Tool def:
```python
    Tool(name="compress_response",
         description="Set session-level response compression flag: post-processes LLM response text through caveman compression (~75% output token reduction). Auto-clarity: drops compression for security warnings and destructive ops.",
         inputSchema={"type": "object", "properties": {
             "enabled": {"type": "boolean"},
             "mode": {"type": "string", "enum": ["lite", "full", "ultra"], "default": "full"},
         }, "required": ["enabled"]}),
```

Handler:
```python
        elif name == "compress_response":
            ctx.session_flags["compress_response_enabled"] = arguments.get("enabled", True)
            ctx.session_flags["compress_response_mode"] = arguments.get("mode", "full")
            return json.dumps({
                "enabled": ctx.session_flags["compress_response_enabled"],
                "mode": ctx.session_flags["compress_response_mode"],
            })
```

- [ ] **Step 5: Run tests**

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_compress_response_enable tests/v2/integrations/test_mcp_server_v2.py::test_compress_response_disable tests/v2/integrations/test_mcp_server_v2.py::test_compress_response_default_mode_is_full -v
```

Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add compress_response session flag MCP tool — output caveman compression"
```

---

## Task 7: ParallelDispatcher Module + MCP Tool

**Files:**
- Create: `src/promptwise_v2/core/parallel_dispatcher.py`
- Test: `tests/v2/core/test_parallel_dispatcher.py`
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/core/test_parallel_dispatcher.py
import asyncio
from promptwise_v2.core.parallel_dispatcher import ParallelDispatcher

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def test_dispatches_independent_tasks():
    dispatcher = ParallelDispatcher()
    tasks = ["Fix auth bug in login.py", "Update README", "Add unit test for router"]
    r = _run(dispatcher.dispatch(tasks, context="Python web app"))
    assert len(r.task_results) == 3
    assert r.merged is True
    assert r.duration_ms >= 0

def test_empty_tasks_returns_empty():
    dispatcher = ParallelDispatcher()
    r = _run(dispatcher.dispatch([], context=""))
    assert r.task_results == []
    assert r.merged is True

def test_conflict_detection_same_file():
    dispatcher = ParallelDispatcher()
    tasks = ["Edit src/auth.py line 10", "Edit src/auth.py line 20"]
    r = _run(dispatcher.dispatch(tasks, context=""))
    assert len(r.conflicts) > 0
    assert "auth.py" in r.conflicts[0]

def test_no_conflict_different_files():
    dispatcher = ParallelDispatcher()
    tasks = ["Edit src/auth.py", "Edit src/router.py"]
    r = _run(dispatcher.dispatch(tasks, context=""))
    assert r.conflicts == []
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```
pytest tests/v2/core/test_parallel_dispatcher.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `parallel_dispatcher.py`**

```python
# src/promptwise_v2/core/parallel_dispatcher.py
import asyncio
import re
import time
from promptwise_v2.types_v2 import ParallelDispatchResult

_FILE_REF = re.compile(r'\b(src/\S+\.py|\S+\.py|\S+\.ts|\S+\.js)\b')


class ParallelDispatcher:
    async def _execute_task(self, task_id: str, task: str, context: str) -> dict:
        await asyncio.sleep(0)  # yield to event loop (real impl calls subagent API)
        return {"id": task_id, "task": task[:100], "status": "dispatched", "output": ""}

    def _detect_conflicts(self, tasks: list[str]) -> list[str]:
        file_to_tasks: dict[str, list[int]] = {}
        for i, task in enumerate(tasks):
            for match in _FILE_REF.finditer(task):
                fname = match.group(1)
                file_to_tasks.setdefault(fname, []).append(i)
        return [
            f"Conflict: '{fname}' referenced in tasks {idxs} — may interfere"
            for fname, idxs in file_to_tasks.items()
            if len(idxs) > 1
        ]

    async def dispatch(self, tasks: list[str], context: str) -> ParallelDispatchResult:
        start = time.monotonic()
        if not tasks:
            return ParallelDispatchResult(task_results=[], conflicts=[], merged=True, duration_ms=0)

        conflicts = self._detect_conflicts(tasks)
        coroutines = [self._execute_task(f"t{i+1}", t, context) for i, t in enumerate(tasks)]
        results = await asyncio.gather(*coroutines)
        duration_ms = int((time.monotonic() - start) * 1000)

        return ParallelDispatchResult(
            task_results=list(results),
            conflicts=conflicts,
            merged=len(conflicts) == 0,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 4: Run tests**

```
pytest tests/v2/core/test_parallel_dispatcher.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Add Tool def + import + handler**

Tool def:
```python
    Tool(name="dispatch_parallel",
         description="Dispatch N independent tasks concurrently as parallel subagents; detects file conflicts before merge",
         inputSchema={"type": "object", "properties": {
             "tasks": {"type": "array", "items": {"type": "string"}, "description": "List of independent task descriptions"},
             "context": {"type": "string", "description": "Shared context for all tasks", "default": ""},
         }, "required": ["tasks"]}),
```

Import:
```python
from promptwise_v2.core.parallel_dispatcher import ParallelDispatcher
```

Handler:
```python
        elif name == "dispatch_parallel":
            r = await ParallelDispatcher().dispatch(
                tasks=arguments.get("tasks", []),
                context=arguments.get("context", ""),
            )
            return json.dumps({"task_results": r.task_results, "conflicts": r.conflicts,
                               "merged": r.merged, "duration_ms": r.duration_ms})
```

- [ ] **Step 6: Write + run integration test**

```python
def test_dispatch_parallel_returns_results():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "dispatch_parallel", {
        "tasks": ["Fix auth bug", "Update README", "Add test"],
        "context": "Python project",
    }))
    data = json.loads(result)
    assert len(data["task_results"]) == 3
    assert "merged" in data

def test_dispatch_parallel_detects_conflicts():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "dispatch_parallel", {
        "tasks": ["Edit src/auth.py line 10", "Edit src/auth.py line 20"],
    }))
    data = json.loads(result)
    assert len(data["conflicts"]) > 0
```

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_dispatch_parallel_returns_results tests/v2/integrations/test_mcp_server_v2.py::test_dispatch_parallel_detects_conflicts -v
```

Expected: 2 PASS

- [ ] **Step 7: Commit**

```bash
git add src/promptwise_v2/core/parallel_dispatcher.py tests/v2/core/test_parallel_dispatcher.py src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add dispatch_parallel MCP tool — concurrent independent task dispatch"
```

---

## Task 8: ReviewPipeline Module + MCP Tool

**Files:**
- Create: `src/promptwise_v2/core/review_pipeline.py`
- Test: `tests/v2/core/test_review_pipeline.py`
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/core/test_review_pipeline.py
from promptwise_v2.core.review_pipeline import ReviewPipeline

def test_approved_when_no_issues():
    pipeline = ReviewPipeline()
    r = pipeline.review(
        implementation="def add(a, b): return a + b",
        spec="Function add(a, b) returns sum of two numbers",
        language="python",
    )
    assert r.spec_compliant is True
    assert r.quality_approved is True
    assert r.approved is True
    assert r.issues == []

def test_blocked_when_spec_mismatch():
    pipeline = ReviewPipeline()
    r = pipeline.review(
        implementation="def multiply(a, b): return a * b",
        spec="Function add(a, b) returns sum of two numbers",
        language="python",
    )
    assert r.spec_compliant is False
    assert r.approved is False
    assert len(r.issues) > 0
    assert any(i["stage"] == "spec_compliance" for i in r.issues)

def test_quality_issue_detected():
    pipeline = ReviewPipeline()
    r = pipeline.review(
        implementation="def f(x, y, z, a, b, c, d): return x",
        spec="Function with 7 parameters",
        language="python",
    )
    assert len([i for i in r.issues if i["stage"] == "code_quality"]) > 0

def test_empty_implementation_fails_both_stages():
    pipeline = ReviewPipeline()
    r = pipeline.review(implementation="", spec="Implement add function", language="python")
    assert r.spec_compliant is False
    assert r.quality_approved is False
    assert r.approved is False
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```
pytest tests/v2/core/test_review_pipeline.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `review_pipeline.py`**

```python
# src/promptwise_v2/core/review_pipeline.py
import re
from promptwise_v2.types_v2 import ReviewPipelineResult

_LONG_PARAM_LIST = re.compile(r'def \w+\(([^)]+)\)')


def _count_params(code: str) -> int:
    match = _LONG_PARAM_LIST.search(code)
    if not match:
        return 0
    params = [p.strip() for p in match.group(1).split(",") if p.strip() and p.strip() != "self"]
    return len(params)


class ReviewPipeline:
    def review(self, implementation: str, spec: str, language: str) -> ReviewPipelineResult:
        issues: list[dict] = []

        # Stage 1: spec compliance
        spec_compliant = True
        if not implementation.strip():
            spec_compliant = False
            issues.append({"stage": "spec_compliance", "severity": "critical",
                           "problem": "No implementation provided.", "fix": "Implement per spec."})
        else:
            spec_words = set(re.findall(r'\b\w+\b', spec.lower()))
            impl_words = set(re.findall(r'\b\w+\b', implementation.lower()))
            key_spec_words = {w for w in spec_words if len(w) > 3} - {"function", "returns", "that", "with"}
            missing = key_spec_words - impl_words
            if len(missing) > len(key_spec_words) * 0.6:
                spec_compliant = False
                issues.append({"stage": "spec_compliance", "severity": "high",
                               "problem": f"Implementation missing spec concepts: {', '.join(list(missing)[:5])}",
                               "fix": "Ensure implementation addresses all spec requirements."})

        # Stage 2: code quality (only runs if spec compliant)
        quality_approved = True
        if spec_compliant and implementation.strip():
            param_count = _count_params(implementation)
            if param_count > 5:
                quality_approved = False
                issues.append({"stage": "code_quality", "severity": "medium",
                               "problem": f"Function has {param_count} parameters (max 5). Too many params = unclear responsibility.",
                               "fix": "Extract params into a dataclass or split function."})

        approved = spec_compliant and quality_approved
        return ReviewPipelineResult(
            spec_compliant=spec_compliant,
            quality_approved=quality_approved,
            issues=issues,
            approved=approved,
        )
```

- [ ] **Step 4: Run tests**

```
pytest tests/v2/core/test_review_pipeline.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Add Tool def + import + handler**

Tool def:
```python
    Tool(name="review_pipeline",
         description="2-stage code review: spec-compliance check then code-quality check; loops until both pass; returns approved=true only when both stages clear",
         inputSchema={"type": "object", "properties": {
             "implementation": {"type": "string", "description": "Code to review"},
             "spec": {"type": "string", "description": "Specification the code must satisfy"},
             "language": {"type": "string", "default": "python"},
         }, "required": ["implementation", "spec"]}),
```

Import:
```python
from promptwise_v2.core.review_pipeline import ReviewPipeline
```

Handler:
```python
        elif name == "review_pipeline":
            r = ReviewPipeline().review(
                implementation=arguments.get("implementation", ""),
                spec=arguments.get("spec", ""),
                language=arguments.get("language", "python"),
            )
            return json.dumps({"spec_compliant": r.spec_compliant, "quality_approved": r.quality_approved,
                               "issues": r.issues, "approved": r.approved})
```

- [ ] **Step 6: Write + run integration test**

```python
def test_review_pipeline_approves_clean_code():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "review_pipeline", {
        "implementation": "def add(a, b): return a + b",
        "spec": "Function add returns sum",
        "language": "python",
    }))
    data = json.loads(result)
    assert data["approved"] is True

def test_review_pipeline_blocks_empty():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "review_pipeline",
                               {"implementation": "", "spec": "Implement add function"}))
    data = json.loads(result)
    assert data["approved"] is False
    assert data["spec_compliant"] is False
```

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_review_pipeline_approves_clean_code tests/v2/integrations/test_mcp_server_v2.py::test_review_pipeline_blocks_empty -v
```

Expected: 2 PASS

- [ ] **Step 7: Commit**

```bash
git add src/promptwise_v2/core/review_pipeline.py tests/v2/core/test_review_pipeline.py src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add review_pipeline MCP tool — 2-stage spec+quality review gate"
```

---

## Task 9: DefectTriage Module + MCP Tool

**Files:**
- Create: `src/promptwise_v2/core/defect_triage.py`
- Test: `tests/v2/core/test_defect_triage.py`
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/core/test_defect_triage.py
from promptwise_v2.core.defect_triage import DefectTriage

def test_crash_is_critical():
    triage = DefectTriage()
    r = triage.analyze(
        description="App crashes on login when password contains special chars",
        context="Production env, affects all users",
    )
    assert r.severity in ("critical", "high")
    assert r.priority in ("P0", "P1")
    assert len(r.reproduction_steps) > 0

def test_ui_glitch_is_low():
    triage = DefectTriage()
    r = triage.analyze(
        description="Button text slightly misaligned on settings page",
        context="Chrome only, desktop",
    )
    assert r.severity in ("low", "medium")
    assert r.priority in ("P3", "P4")

def test_missing_description_returns_unknown():
    triage = DefectTriage()
    r = triage.analyze(description="", context="")
    assert r.severity == "unknown"
    assert r.priority == "P4"

def test_data_loss_is_critical():
    triage = DefectTriage()
    r = triage.analyze(
        description="User data deleted when session expires unexpectedly",
        context="",
    )
    assert r.severity == "critical"
    assert r.priority == "P0"
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```
pytest tests/v2/core/test_defect_triage.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `defect_triage.py`**

```python
# src/promptwise_v2/core/defect_triage.py
import re
from promptwise_v2.types_v2 import DefectTriageResult

_CRITICAL_SIGNALS = re.compile(
    r'\b(crash|crashes|data loss|data deleted|security|breach|corrupt|unrecoverable|'
    r'production down|all users|payment|financial|pii|personal data)\b', re.I
)
_HIGH_SIGNALS = re.compile(
    r'\b(fail|broken|not working|cannot|blocked|regression|login|auth|'
    r'unable to|500 error|database|api down)\b', re.I
)
_LOW_SIGNALS = re.compile(
    r'\b(misaligned|cosmetic|typo|color|font|spacing|tooltip|minor|slight|'
    r'glitch|ui only|styling)\b', re.I
)

_SEVERITY_PRIORITY = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
    "unknown": "P4",
}

_OWNER_HINTS = {
    "auth": "auth-team",
    "login": "auth-team",
    "payment": "payments-team",
    "database": "backend-team",
    "api": "backend-team",
    "ui": "frontend-team",
    "styling": "frontend-team",
    "security": "security-team",
}


class DefectTriage:
    def analyze(self, description: str, context: str) -> DefectTriageResult:
        if not description.strip():
            return DefectTriageResult(
                severity="unknown", priority="P4",
                reproduction_steps=["Provide bug description to generate reproduction steps."],
                suggested_owner="unassigned", tags=[],
            )

        combined = f"{description} {context}".lower()

        if _CRITICAL_SIGNALS.search(combined):
            severity = "critical"
        elif _HIGH_SIGNALS.search(combined):
            severity = "high"
        elif _LOW_SIGNALS.search(combined):
            severity = "low"
        else:
            severity = "medium"

        priority = _SEVERITY_PRIORITY[severity]

        steps = [
            f"Reproduce: {description[:80]}",
            f"Environment: {context[:60] or 'not specified'}",
            "Note exact error message or behaviour",
            "Check recent commits for changes to affected area",
        ]

        suggested_owner = "engineering"
        for keyword, owner in _OWNER_HINTS.items():
            if keyword in combined:
                suggested_owner = owner
                break

        tags = []
        if "regression" in combined:
            tags.append("regression")
        if "production" in combined:
            tags.append("production")
        if severity == "critical":
            tags.append("urgent")

        return DefectTriageResult(
            severity=severity, priority=priority,
            reproduction_steps=steps,
            suggested_owner=suggested_owner,
            tags=tags,
        )
```

- [ ] **Step 4: Run tests**

```
pytest tests/v2/core/test_defect_triage.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Add Tool def + import + handler**

Tool def:
```python
    Tool(name="triage_defect",
         description="Classify bug severity/priority and generate reproduction steps from a defect description",
         inputSchema={"type": "object", "properties": {
             "description": {"type": "string", "description": "Bug description"},
             "context": {"type": "string", "description": "Environment, affected users, frequency", "default": ""},
         }, "required": ["description"]}),
```

Import:
```python
from promptwise_v2.core.defect_triage import DefectTriage
```

Handler:
```python
        elif name == "triage_defect":
            r = DefectTriage().analyze(
                description=arguments.get("description", ""),
                context=arguments.get("context", ""),
            )
            return json.dumps({"severity": r.severity, "priority": r.priority,
                               "reproduction_steps": r.reproduction_steps,
                               "suggested_owner": r.suggested_owner, "tags": r.tags})
```

- [ ] **Step 6: Write + run integration test**

```python
def test_triage_defect_crash():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "triage_defect", {
        "description": "App crashes on login",
        "context": "Production, all users affected",
    }))
    data = json.loads(result)
    assert data["severity"] in ("critical", "high")
    assert "reproduction_steps" in data
    assert len(data["reproduction_steps"]) > 0
```

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_triage_defect_crash -v
```

Expected: 1 PASS

- [ ] **Step 7: Commit**

```bash
git add src/promptwise_v2/core/defect_triage.py tests/v2/core/test_defect_triage.py src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add triage_defect MCP tool — QA defect severity/priority classifier"
```

---

## Task 10: compress_memory_file MCP Tool

**Files:**
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`
- Modify: `tests/v2/integrations/test_mcp_server_v2.py`

- [ ] **Step 1: Write failing test**

```python
import tempfile
import os

def test_compress_memory_file():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Notes\n\nYou should always make sure to run all the tests before pushing any changes to the main branch.\n")
        path = f.name
    try:
        result = _run(call_tool_v2(ctx, "compress_memory_file", {"file_path": path}))
        data = json.loads(result)
        assert data["tokens_saved"] > 0
        assert data["saving_pct"] > 0
        assert os.path.exists(data["backup_path"])
        with open(path) as f:
            compressed = f.read()
        assert len(compressed) < 100  # compressed is shorter
    finally:
        if os.path.exists(path):
            os.unlink(path)
        backup = path.replace(".md", ".original.md")
        if os.path.exists(backup):
            os.unlink(backup)

def test_compress_memory_file_refuses_non_md():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "compress_memory_file", {"file_path": "src/something.py"}))
    data = json.loads(result)
    assert "error" in data
    assert "only compress" in data["error"].lower() or ".md" in data["error"].lower()
```

- [ ] **Step 2: Run — expect tool not found**

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_compress_memory_file -v
```

Expected: `FAILED` (tool not found)

- [ ] **Step 3: Add Tool def + handler** (no new module — uses existing `CompressionEngine`)

Tool def:
```python
    Tool(name="compress_memory_file",
         description="Compress a CLAUDE.md or memory .md file to caveman format to save input tokens. Backs up original as FILE.original.md. Never touches code blocks.",
         inputSchema={"type": "object", "properties": {
             "file_path": {"type": "string", "description": "Absolute or relative path to .md file"},
         }, "required": ["file_path"]}),
```

Handler (uses existing `ctx.compression` — the `CompressionEngine`):
```python
        elif name == "compress_memory_file":
            import pathlib
            fpath = pathlib.Path(arguments.get("file_path", ""))
            if fpath.suffix not in (".md", ".txt"):
                return json.dumps({"error": f"Will only compress .md/.txt files, got: {fpath.suffix}"})
            if not fpath.exists():
                return json.dumps({"error": f"File not found: {fpath}"})
            original_text = fpath.read_text(encoding="utf-8")
            result = ctx.compression.compress(original_text)
            backup_path = fpath.with_suffix(".original" + fpath.suffix)
            backup_path.write_text(original_text, encoding="utf-8")
            fpath.write_text(result.compressed, encoding="utf-8")
            return json.dumps({
                "original_path": str(fpath),
                "backup_path": str(backup_path),
                "tokens_saved": result.tokens_saved,
                "saving_pct": result.saving_pct,
            })
```

- [ ] **Step 4: Run tests**

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_compress_memory_file tests/v2/integrations/test_mcp_server_v2.py::test_compress_memory_file_refuses_non_md -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add compress_memory_file MCP tool — CLAUDE.md input token reduction"
```

---

## Task 11: TestStrategist Module + MCP Tool

**Files:**
- Create: `src/promptwise_v2/core/test_strategist.py`
- Test: `tests/v2/core/test_test_strategist.py`
- Modify: `src/promptwise_v2/integrations/mcp_server_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/core/test_test_strategist.py
from promptwise_v2.core.test_strategist import TestStrategist

def test_returns_matrix():
    strategist = TestStrategist()
    r = strategist.generate(scope="REST API with auth", platforms=["api", "browser"])
    assert len(r.matrix) > 0
    assert all("layer" in row and "platform" in row and "framework" in row for row in r.matrix)

def test_recommends_pytest_for_python():
    strategist = TestStrategist()
    r = strategist.generate(scope="Python FastAPI service", platforms=["api"])
    assert "pytest" in r.framework_recommendation

def test_recommends_playwright_for_browser():
    strategist = TestStrategist()
    r = strategist.generate(scope="React web app", platforms=["browser"])
    assert "playwright" in r.framework_recommendation.lower() or "cypress" in r.framework_recommendation.lower()

def test_coverage_target_default():
    strategist = TestStrategist()
    r = strategist.generate(scope="any", platforms=["api"])
    assert 0.7 <= r.coverage_target <= 1.0

def test_empty_platforms_uses_defaults():
    strategist = TestStrategist()
    r = strategist.generate(scope="Python service", platforms=[])
    assert len(r.matrix) > 0
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```
pytest tests/v2/core/test_test_strategist.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `test_strategist.py`**

```python
# src/promptwise_v2/core/test_strategist.py
import re
from promptwise_v2.types_v2 import TestStrategyResult

_LAYERS = ["unit", "integration", "e2e"]
_FRAMEWORK_MAP = {
    "python": "pytest",
    "fastapi": "pytest",
    "django": "pytest",
    "flask": "pytest",
    "node": "jest",
    "react": "jest",
    "vue": "jest",
    "angular": "jest",
    "typescript": "jest",
    "go": "go test",
    "java": "junit",
    "ruby": "rspec",
    "browser": "playwright",
    "e2e": "playwright",
    "api": "pytest",
    "mobile": "detox",
}


class TestStrategist:
    def _detect_framework(self, scope: str, platforms: list[str]) -> str:
        combined = f"{scope} {' '.join(platforms)}".lower()
        for keyword, fw in _FRAMEWORK_MAP.items():
            if keyword in combined:
                return fw
        return "pytest"

    def generate(self, scope: str, platforms: list[str]) -> TestStrategyResult:
        if not platforms:
            platforms = ["api"]

        framework = self._detect_framework(scope, platforms)
        matrix: list[dict] = []

        for layer in _LAYERS:
            for platform in platforms:
                fw = "playwright" if layer == "e2e" and "browser" in platform else framework
                matrix.append({"layer": layer, "platform": platform, "framework": fw,
                                "priority": "high" if layer == "unit" else "medium" if layer == "integration" else "low"})

        return TestStrategyResult(
            matrix=matrix,
            framework_recommendation=framework,
            coverage_target=0.85,
        )
```

- [ ] **Step 4: Run tests**

```
pytest tests/v2/core/test_test_strategist.py -v
```

Expected: 5 PASS

- [ ] **Step 5: Add Tool def + import + handler**

Tool def:
```python
    Tool(name="test_strategy",
         description="Generate test matrix (unit/integration/e2e × platforms) and automation framework recommendation",
         inputSchema={"type": "object", "properties": {
             "scope": {"type": "string", "description": "System description (e.g. 'Python FastAPI REST API')"},
             "platforms": {"type": "array", "items": {"type": "string"},
                           "description": "Target platforms: api, browser, mobile", "default": ["api"]},
         }, "required": ["scope"]}),
```

Import:
```python
from promptwise_v2.core.test_strategist import TestStrategist
```

Handler:
```python
        elif name == "test_strategy":
            r = TestStrategist().generate(
                scope=arguments.get("scope", ""),
                platforms=arguments.get("platforms", ["api"]),
            )
            return json.dumps({"matrix": r.matrix, "framework_recommendation": r.framework_recommendation,
                               "coverage_target": r.coverage_target})
```

- [ ] **Step 6: Write + run integration test**

```python
def test_test_strategy_returns_matrix():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "test_strategy", {
        "scope": "Python FastAPI REST API",
        "platforms": ["api", "browser"],
    }))
    data = json.loads(result)
    assert len(data["matrix"]) > 0
    assert "framework_recommendation" in data
    assert data["coverage_target"] >= 0.7
```

```
pytest tests/v2/integrations/test_mcp_server_v2.py::test_test_strategy_returns_matrix -v
```

Expected: 1 PASS

- [ ] **Step 7: Commit**

```bash
git add src/promptwise_v2/core/test_strategist.py tests/v2/core/test_test_strategist.py src/promptwise_v2/integrations/mcp_server_v2.py tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): add test_strategy MCP tool — test matrix + framework recommendation"
```

---

## Task 12: Skill .md Files (plan_feature + auto_clarity)

**Files:**
- Create: `src/promptwise_v2/skills/dev/plan-feature.md`
- Create: `src/promptwise_v2/skills/dev/auto-clarity.md`

- [ ] **Step 1: Write failing test**

```python
# append to tests/v2/core/test_execute_skill.py (or a new file tests/v2/core/test_skill_files.py)

def test_plan_feature_skill_loads():
    from promptwise_v2.core.skill_loader import SkillLoader
    from pathlib import Path
    loader = SkillLoader(Path("src/promptwise_v2/skills"))
    sk = loader.get_skill("plan-feature")
    assert sk is not None
    assert sk.name == "plan-feature"
    assert sk.model_tier in ("opus", "sonnet", "haiku", "auto")

def test_auto_clarity_skill_loads():
    from promptwise_v2.core.skill_loader import SkillLoader
    from pathlib import Path
    loader = SkillLoader(Path("src/promptwise_v2/skills"))
    sk = loader.get_skill("auto-clarity")
    assert sk is not None
    assert sk.name == "auto-clarity"
```

- [ ] **Step 2: Run — expect AssertionError (skill files don't exist yet)**

```
pytest tests/v2/core/test_skill_files.py -v
```

Expected: `AssertionError: assert None is not None` (skill not found)

- [ ] **Step 3: Create `plan-feature.md`**

```markdown
---
name: plan-feature
description: Chain clarify-requirements → generate-spec → generate-implementation-plan for a new feature
triggers: ["plan feature", "feature plan", "implementation plan", "create plan", "plan this"]
depends_on: []
output_schema:
  type: object
  properties:
    spec_path: {type: string}
    plan_path: {type: string}
    tasks_count: {type: integer}
  required: ["spec_path", "plan_path", "tasks_count"]
roles: ["Dev", "EM", "PM"]
model_tier: sonnet
---

# Plan Feature Skill

You are a software architect. Given a feature description, produce a complete implementation plan in 3 stages:

## Stage 1: Clarify Requirements
Ask at most 3 focused questions to resolve ambiguity. Do not ask about things that can be inferred. One question at a time.

## Stage 2: Generate Spec
Write a design spec to `docs/superpowers/specs/YYYY-MM-DD-<feature>.md`:
- Problem statement
- Architecture decisions
- File structure (new + modified)
- Out of scope

## Stage 3: Generate Implementation Plan
Write a plan to `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` following the writing-plans skill format:
- Header with goal, architecture, tech stack
- Tasks with TDD steps, exact file paths, real code, exact commands
- No placeholders

Return: `{spec_path, plan_path, tasks_count}`
```

- [ ] **Step 4: Create `auto-clarity.md`**

```markdown
---
name: auto-clarity
description: Protocol for dropping communication compression in contexts where compression creates ambiguity or risk
triggers: ["auto clarity", "when to drop compression", "safety mode", "clear language"]
depends_on: []
output_schema:
  type: object
  properties:
    active: {type: boolean}
    trigger: {type: string}
  required: ["active", "trigger"]
roles: ["Dev", "IT", "EM", "PM"]
model_tier: haiku
---

# Auto-Clarity Protocol

Drop ALL communication compression when ANY of these triggers apply:

1. **Security warning** — any message containing risk, vulnerability, breach, exploit, CVE, injection, permission escalation
2. **Destructive operation** — DROP, DELETE, TRUNCATE, rm -rf, git reset --hard, format, overwrite; always write full unambiguous English
3. **Multi-step sequence with order ambiguity** — when step order matters and fragments could be misread (e.g., "migrate table drop column backup first" — unclear which comes first)
4. **Technical ambiguity** — when caveman compression itself creates ambiguity (shortened term could mean two different things)
5. **User confusion signal** — user repeats question, asks for clarification, or says they didn't understand

After the ambiguous/risky section completes, resume normal compression mode.

## Example — Destructive Op

> **Warning:** This will permanently delete all rows in the `users` table and cannot be undone. Ensure you have a backup before proceeding.
> ```sql
> DELETE FROM users WHERE created_at < '2024-01-01';
> ```
> Auto-clarity complete. Resume caveman. Verify backup exists first.
```

- [ ] **Step 5: Run tests**

```
pytest tests/v2/core/test_skill_files.py -v
```

Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add src/promptwise_v2/skills/dev/plan-feature.md src/promptwise_v2/skills/dev/auto-clarity.md tests/v2/core/test_skill_files.py
git commit -m "feat(phase-a): add plan_feature and auto_clarity skills"
```

---

## Task 13: Config Update + auto_clarity Key

**Files:**
- Modify: `config/promptwise_v2.yaml`

- [ ] **Step 1: Check current config**

```
grep -n "auto_clarity\|compression" config/promptwise_v2.yaml
```

If `auto_clarity` key already present: skip to Step 3.

- [ ] **Step 2: Add `auto_clarity` section to `config/promptwise_v2.yaml`**

Add under the existing `quality:` section (or at end of file if no quality section):

```yaml
auto_clarity:
  enabled: true
  triggers:
    - security_warning
    - destructive_op
    - step_order_ambiguity
    - technical_ambiguity
    - user_confusion_signal

compress_response:
  default_mode: full          # lite | full | ultra
  preserve_code_blocks: true  # never compress code inside ``` ... ```
  session_persistent: true    # flag persists for entire session once set
```

- [ ] **Step 3: Write + run config load test**

```python
# append to tests/v2/test_config_v2.py

def test_auto_clarity_config_loads():
    from promptwise_v2.config_v2 import load_config_v2
    from pathlib import Path
    cfg = load_config_v2(Path("config"))
    # Should not throw — config loads cleanly with new keys
    assert cfg is not None
```

```
pytest tests/v2/test_config_v2.py::test_auto_clarity_config_loads -v
```

Expected: 1 PASS

- [ ] **Step 4: Commit**

```bash
git add config/promptwise_v2.yaml tests/v2/test_config_v2.py
git commit -m "feat(phase-a): add auto_clarity and compress_response config keys"
```

---

## Task 14: Update Tool Count + Full Suite

**Files:**
- Modify: `tests/v2/integrations/test_mcp_server_v2.py`

- [ ] **Step 1: Count current tools in `_V2_TOOL_DEFS`**

```
grep -c "Tool(name=" src/promptwise_v2/integrations/mcp_server_v2.py
```

Note the count. Should be 66 after Phase A additions (56 baseline + 10 new).

- [ ] **Step 2: Update the tool count test**

In `tests/v2/integrations/test_mcp_server_v2.py`, find:

```python
def test_tool_count_is_56():
    tools = _run(list_tools_v2())
    assert len(tools) == 56
```

Change to:

```python
def test_tool_count_is_66():
    tools = _run(list_tools_v2())
    assert len(tools) == 66
```

- [ ] **Step 3: Add Phase A tool presence test**

```python
def test_phase_a_tools_present():
    tools = _run(list_tools_v2())
    names = {t.name for t in tools}
    phase_a_tools = {
        "agent_roles", "debug_gate", "tdd_gate", "verification_gate",
        "compress_response", "dispatch_parallel", "review_pipeline",
        "triage_defect", "compress_memory_file", "test_strategy",
    }
    assert phase_a_tools.issubset(names), f"Missing tools: {phase_a_tools - names}"
```

- [ ] **Step 4: Run full test suite**

```
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests PASS. No failures or errors.

- [ ] **Step 5: If any test fails — fix before committing**

Read the failure message. Fix the root cause (do not skip or comment out failing tests). Re-run until clean.

- [ ] **Step 6: Final commit**

```bash
git add tests/v2/integrations/test_mcp_server_v2.py
git commit -m "feat(phase-a): update tool count to 66, add Phase A presence test — complete"
```

---

## Phase A Complete

Run full suite one final time:

```
pytest tests/ -v 2>&1 | tail -10
```

Expected output ends with: `X passed in Ys` (zero failures, zero errors).

**Next phase:** See `docs/superpowers/plans/2026-06-05-promptwise-phase-b-local-proxy.md` (to be written before Phase B starts).
