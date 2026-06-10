# PromptWise — Coding Agent Platform Design Spec

**Date:** 2026-06-05
**Scope:** Feature additions (12 tools/skills) + bidirectional middleware integrations (local proxy, VS Code, browser extension)
**Baseline:** PromptWise v3.5 (36 MCP tools, 39 skills, individual-complete)
**Goal:** PromptWise as universal coding agent middleware — enforces dev workflows, optimizes tokens, routes across providers, integrates into Claude Chat / ChatGPT / Gemini / VS Code

---

## 1. Problem Statement

PromptWise v3 excels at cost optimization and skill execution. Gaps vs peer plugins:

| Domain | Gap |
|--------|-----|
| Output token reduction | Has input compression. No output/response compression mode |
| Dev workflow enforcement | No TDD gate, no systematic debug gate, no completion evidence gate |
| Agent coordination | Sequential DAG only. No parallel dispatch. No 2-stage review pipeline |
| QA integration | No defect triage, no test strategy matrix |
| Platform reach | Claude Code CLI only. No browser, no proxy, no VS Code |

---

## 2. Design Decisions

### 2.1 Feature Additions (Phase A)

Adopt proven patterns from caveman, superpowers, and QA plugins as native PromptWise MCP tools and skills.

**Tier 1 — Dev workflow gates (highest coding agent impact):**

| Tool/Skill | Source pattern | Behaviour |
|------------|---------------|-----------|
| `compress_response` | caveman output mode | Session flag; post-processes LLM response text through compression engine (same rules as caveman:compress — drop articles/filler, fragments OK, preserve code blocks exactly); ~75% output token reduction; auto-clarity: drops compression for security warnings and destructive ops |
| `debug_gate` | superpowers:systematic-debugging | 4-phase enforcement: reproduce → evidence → hypothesis → fix; blocks fix attempts without root cause |
| `tdd_gate` | superpowers:test-driven-development | Iron law gate: rejects implementation requests without prior failing-test proof |
| `verification_gate` | superpowers:verification-before-completion | Evidence-required gate before any completion claim; runs fresh check command, reads output |
| `agent_roles` | caveman cavecrew pattern | Returns pre-built agent prompt templates: `builder` (1-2 file surgical), `investigator` (read-only search), `reviewer` (diff + severity-tagged findings) |

**Tier 2 — Agent coordination + QA:**

| Tool/Skill | Source pattern | Behaviour |
|------------|---------------|-----------|
| `dispatch_parallel` | superpowers:dispatching-parallel-agents | Splits N independent tasks → concurrent subagent dispatch; returns results array; conflict check before merge |
| `review_pipeline` | superpowers:subagent-driven-development | 2-stage: spec-compliance review → code-quality review; loops until both pass |
| `triage_defect` | QA skill | Input: bug description + context; output: `{severity, priority, reproduction_steps, suggested_owner}` |
| `compress_memory_file` | caveman:compress | Compresses CLAUDE.md / memory .md files to caveman format; backs up as `FILE.original.md`; never touches code blocks |
| `test_strategy` | QA skill | Input: scope + platforms; output: test matrix (unit/integration/e2e × browser/mobile/API) + automation framework recommendation |

**Tier 3 — Pipeline + config:**

| Tool/Skill | Source pattern | Behaviour |
|------------|---------------|-----------|
| `plan_feature` | superpowers brainstorm→plan chain | Chains: clarify requirements → generate spec → generate implementation plan; saves to `docs/superpowers/` |
| `auto_clarity` config | caveman auto-clarity protocol | Config flag: drops all compression for security warnings, destructive ops, multi-step sequences with order ambiguity |

### 2.2 Local Proxy Server (Phase B)

PromptWise as `localhost:8765` HTTP proxy. All clients (API callers, CLI tools, browser ext, VS Code) route through it.

```
Client request
    ↓
[Pre-processing pipeline]
  - compress_response (if session flag set)
  - rewrite_prompt (if verbose)
  - route_request (model selection)
  - debug_gate / tdd_gate (if coding request detected)
  - security_check (always)
    ↓
[Provider router]
  - Anthropic API  → api.anthropic.com
  - OpenAI API     → api.openai.com
  - Gemini API     → generativelanguage.googleapis.com
    ↓
[Post-processing pipeline]
  - scan_response (OWASP, PII)
  - validate_output (code syntax)
  - verification_gate (if completion claim detected)
  - track session stats, cost, budget
    ↓
Client response
```

**Implementation:**
- FastAPI app, async throughout
- Per-provider auth forwarding (pass-through; keys never stored)
- Pre/post pipeline: configurable per-session via `promptwise_v2.yaml`
- Dashboard endpoint: `GET /dashboard` returns session stats JSON
- Config endpoint: `POST /config` hot-reloads pipeline settings

### 2.3 VS Code Extension (Phase C)

Wraps local proxy + existing MCP server. No new Python.

**Features:**
- Auto-starts local proxy on workspace open
- All MCP tools as VS Code commands (`Ctrl+Shift+P → PromptWise: <tool>`)
- Status bar: live cost + active model + compress_response mode indicator
- Webview panel: session stats dashboard (reuses `/dashboard` endpoint)
- Per-workspace `model_strategy.yaml` overrides
- Hooks: pre-save runs `tdd_gate` / `verification_gate` if configured

### 2.4 Browser Extension (Phase D)

Manifest V3. Intercepts fetch calls to provider APIs from web UIs.

**Supported surfaces:**
- `claude.ai` — intercepts `/api/append_message`
- `chatgpt.com` — intercepts `/backend-api/conversation`
- `gemini.google.com` — intercepts `/api/generate`

**Architecture:**
```
Content script (per domain)
  - Intercepts outbound fetch
  - Sends to background service worker
    ↓
Background service worker
  - Forwards to local proxy at localhost:8765
  - Receives processed request/response
  - Returns to content script
    ↓
Content script
  - Injects processed content into original request
  - Optionally overlays cost/token stats in UI
```

**Popup UI:** On/off toggle, compress_response toggle, current session cost, model in use.

> **Risk:** Provider API endpoints (`/api/append_message`, `/backend-api/conversation`, etc.) change without notice. Implementation must version-pin intercept patterns and include a fallback passthrough mode. Endpoint config stored in updatable JSON, not hardcoded.

---

## 3. Build Priority

| Phase | What | Why first |
|-------|------|----------|
| **A** | PromptWise feature additions (12 tools/skills) | Core capabilities; proxy/ext are delivery mechanisms — build what they deliver first |
| **B** | Local proxy server | Shared backbone; VS Code and browser ext both depend on it |
| **C** | VS Code extension | Primary coding agent surface; highest dev workflow impact |
| **D** | Browser extension | Widest reach; last because depends on proxy being stable |

---

## 4. Architecture Principles

- **No breaking changes:** All existing 36 tools / 39 skills preserved; new tools additive only
- **Proxy is optional:** PromptWise works standalone (Claude Code CLI) without proxy running
- **Auth pass-through only:** Keys never stored in proxy; forwarded per-request
- **Pipeline configurable:** Each pre/post step individually toggleable in `promptwise_v2.yaml`
- **auto_clarity always on:** Compression drops automatically for security warnings and destructive ops regardless of session flags

---

## 5. New Tool/Skill Count

| Phase | New tools | New skills | Cumulative tools | Cumulative skills |
|-------|-----------|------------|-----------------|-------------------|
| Baseline v3.5 | — | — | 36 | 39 |
| Phase A | +10 | +2 | 46 | 41 |
| Phase B | +2 (proxy_status, pipeline_config) | 0 | 48 | 41 |
| Phase C | +1 (vscode_command) | 0 | 49 | 41 |
| Phase D | +1 (browser_ext_status) | 0 | 50 | 41 |
| **Total** | | | **50** | **41** |

---

## 6. Effort Estimates

| Phase | Calendar (full-time) | Tokens | Est. cost |
|-------|---------------------|--------|-----------|
| A — Feature additions | 3-5 days | ~330K | ~$2-3 |
| B — Local proxy | 5-7 days | ~400K | ~$3-4 |
| C — VS Code extension | 7-10 days | ~500K | ~$4-5 |
| D — Browser extension | 8-12 days | ~600K | ~$5-6 |
| Integration testing | 3-5 days | ~200K | ~$1-2 |
| **Total** | **4-6 weeks** | **~2M** | **~$15-20** |

---

## 7. Out of Scope

- Renaming plugin (deferred; `PromptWise` retained for now)
- LLM backends other than Anthropic/OpenAI/Gemini
- Mobile clients
- Team/enterprise features (already in v3.6-v3.7 roadmap)
