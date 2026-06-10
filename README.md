# PromptWise v2.0.0 – Multi-Platform Token Optimization

Token-aware prompt routing with **auto-role detection** and **multi-platform support**. 

🎯 **9 core tools** + 16 auto-detected roles + 4 platforms (MCP, Codex 5.5, Gemini, Antigravity)

Cost optimization: routing, caching, compression, batching, cross-provider comparison, and stats.

## Install

**Windows:**
```bat
install.bat
```

**macOS / Linux:**
```bash
python install.py
```

Both run `pip install -e .`, then register via `claude mcp add` (fallback: patch `~/.claude/settings.json`).

Restart Claude Code. Run `/mcp` — promptwise tools appear in list.

### Corporate proxy / SSL errors

If install fails with `SSLCertVerificationError: self-signed certificate in certificate chain`, your network proxy intercepts HTTPS. The installer handles this automatically by writing pip trusted-host config before running pip. If you need to fix it manually:

**Windows** — create `%APPDATA%\pip\pip.ini`:
```ini
[global]
trusted-host = pypi.org
	files.pythonhosted.org
	pypi.python.org
```

**macOS / Linux** — create `~/.config/pip/pip.conf` with the same content.

> **Note:** File must be saved as UTF-8 **without BOM**. PowerShell's default encoding adds a BOM — use `[System.IO.File]::WriteAllText()` or Python to write it.

---

## Multi-Platform Support

| Platform | Status | Best For | Setup |
|----------|--------|----------|-------|
| **MCP (Claude Code)** | ✅ Default | Local development, Claude Code | No setup required |
| **Codex 5.5** | ✅ Production | Code generation, refactoring | `export CODEX_API_KEY=sk_...` |
| **Google Gemini** | ✅ Production | General-purpose AI, multimodal | `export GEMINI_API_KEY=AIza...` |
| **Antigravity CLI** | 🔲 Pending | Internal agentic tools | Requires API spec |

**Quick start:**
```bash
# Use with Gemini
export PROMPTWISE_PLATFORM=gemini
export GEMINI_API_KEY="AIzaSy_..."
python -m promptwise.server
```

See [Multi-Platform Guide](docs/integration/MULTI_PLATFORM.md) for details.

## Auto-Role Detection

PromptWise automatically detects your role from prompts and applies context-aware optimization:

**Detected roles (16 total):**
developer, analyst, manager, security, IT, designer, writer, researcher, pm, legal, healthcare, finance, data, qa, executive, general

**Example:**
```python
from promptwise_v2.core.auto_role_applier import AutoRoleApplier

applier = AutoRoleApplier(detector, roles_config)
result = applier.apply("Refactor the auth module")
# → Detects: "developer" role (0.95 confidence)
# → Applies: "From a software engineering perspective, ..."
# → Constraints: code blocks, imports, syntax validation
```

## Tools

### route_request
Pick right Claude tier by intent, stakes, context, and budget.

**When:** "which model should I use", budget concern, production vs. test, prompt is large.

**Returns:** recommended_model, reason, intent_detected, stakes_detected, estimated_input_cost_usd, estimated_output_cost_usd, context_window_pct, context_window_warning, alternatives, peak_hour_warning.

**Example:**
```
Text: "Analyze 50-page legal doc for compliance violations"
Intent: analysis  Stakes: high
→ claude-opus-4-7
  context_window_pct: 4.2%
  estimated_input: $0.000240  estimated_output: $0.000240
```

---

### compare_providers
Compare cost of same request across Claude, OpenAI, and Gemini. Sorted by total cost.

**When:** "is this cheaper on GPT?", multi-provider evaluation, cost-sensitive workload.

**Example:**
```
Text: "Summarize this document" (350 tokens)

Provider      Tier       Model                   Total cost
gemini        fast       gemini-2.0-flash        $0.000035
openai        fast       gpt-4o-mini             $0.000053
gemini        balanced   gemini-2.5-pro          $0.000438
claude        fast       claude-haiku-4-5        $0.000350
openai        balanced   gpt-4o                  $0.000875
...
```

---

### rewrite_prompt
Strip filler ("could you please") and preambles. Apply role prefix.

**When:** Verbose prompt, too many pleasantries, role-specific framing needed.

**Example:**
```
Original (89 tokens):
"I was wondering if you could perhaps help me rewrite this code
to be more Pythonic. I'd really appreciate it if you could
focus on readability."

Rewritten (42 tokens):
"From a software engineering perspective, rewrite for Pythonic
style and readability."

Saves: 53%
```

---

### optimize_context
Fit large document into token budget. Scores chunks by position + keyword density + headers. Never drops code blocks.

**When:** Long doc pasted, "this is too long", context exceeds budget.

**Example:**
```
Input: 8,000-token legal agreement   Budget: 2,000 tokens
→ Drops appendices/examples. Keeps: terms, liability, payment.
Saves: 75%   chunks_dropped: 6
```

---

### plan_cache
Design cache breakpoints for repeated calls (RAG, chatbots, agentic loops).

**When:** Same system prompt / docs sent many times.

**Returns:** breakpoints with message_index, ttl (1h or 5m), rationale, savings_pct.

**Example:**
```
Messages: system(2K) + doc(8K) + user(500)   Reuse: 10x
→ Cache system at index 0 (1h), doc at index 1 (1h)
Saves: 77% on subsequent turns
```

---

### batch_prompts
Merge 2–5 related small tasks into one prompt.

**When:** Multiple related tasks ("also summarize...", "then classify...").

**Example:**
```
Task 1: "Summarize this email"
Task 2: "Extract sender and date"
Task 3: "Flag urgent items"
→ Batched with connectives ("Also,", "Then,")
Saves: ~45%
```

---

### summarize_thread
Compress long conversation for fresh chat. Keeps decisions, recent context.

**When:** Conversation approaching context limit, wrapping long session.

**Returns:** summary, reset_prompt (ready for new session), saving_pct.

---

### get_session_stats
Cost, savings, cache hit rate, model distribution. Stale-pricing warning if pricing.yaml >90 days old.

**When:** "How much did I spend?", periodic cost check.

**Example:**
```json
{
  "total_calls": 47,
  "total_cost_usd": 0.38,
  "total_savings_usd": 0.084,
  "avg_saving_pct": 22.1,
  "cache_hit_rate": 0.18,
  "calls_by_tool": {"rewrite_prompt": 12, "route_request": 8, ...},
  "cost_by_model": {"claude-sonnet-4-6": 0.29, ...},
  "pricing_age_days": 2,
  "stale_pricing_warning": null
}
```

---

### reload_config
Reload pricing.yaml, providers.yaml, roles.yaml without restarting server.

**When:** Updated YAML configs, refreshed pricing.

---

## CLI Commands

```bash
# MCP server (called by Claude Code automatically)
python -m promptwise.server

# Session stats in terminal
promptwise stats

# Rewrite quality eval report
promptwise eval
```

---

## Config Files

| File | Purpose |
|------|---------|
| `pricing.yaml` | Per-model rates (input, output, cache_write, cache_hit, batch). Claude + OpenAI + Gemini. |
| `providers.yaml` | Provider tiers (fast/balanced/powerful), peak hours, feature warnings. |
| `roles.yaml` | Role prefixes, preamble phrases to strip, filler words. |

**Important:** Update `last_verified` date in `pricing.yaml` after verifying rates. `get_session_stats` warns if >90 days stale.

Schema defined in `src/promptwise/config.py`.

---

## Stats

Logged to `~/.promptwise/history.db` (SQLite, persists across sessions).

- `cache_hit_rate` = cached_input_tokens / total_input_tokens
- `avg_saving_pct` = average token reduction across all optimization calls
- `total_savings_usd` ≈ cost_usd × avg_saving_pct

---

## Tests

```bash
pytest tests/ -v
```

93 tests, 0 warnings. All pass. Covers all 9 services + MCP server smoke tests.

---

## Supported Models

| Provider | Fast | Balanced | Powerful |
|---------|------|----------|---------|
| Claude | Haiku 4.5 | Sonnet 4.6 | Opus 4.7 |
| OpenAI | GPT-4o mini | GPT-4o | o3 |
| Gemini | 2.0 Flash | 2.5 Pro | 2.5 Pro Thinking |
| **Codex 5.5** | **base** | **pro** | **max** |

**New (v2.0.0):** Codex 5.5 support for code generation and refactoring.

Pricing in `pricing.yaml`. OpenAI/Gemini rates marked "approximate" — verify at provider pricing pages before production use.

## Documentation

- **[Multi-Platform Integration Guide](docs/integration/MULTI_PLATFORM.md)** — Use PromptWise with Codex, Gemini, or MCP
- **[Codex 5.5 Integration](docs/integration/CODEX.md)** — Code generation, refactoring, model tier selection
- **[Architecture Review](READINESS_REVIEW.md)** — Deep dive on design and implementation
- **[Implementation Roadmap](IMPLEMENTATION_ROADMAP.md)** — Phase-by-phase breakdown of features

## Configuration

**Enable auto-role detection (default: true):**
```bash
export PROMPTWISE_AUTO_ROLE=true
export PROMPTWISE_AUTO_ROLE_THRESHOLD=0.65
```

**Choose platform (default: mcp):**
```bash
export PROMPTWISE_PLATFORM=mcp|codex|gemini|antigravity
```

**Set API keys:**
```bash
export GEMINI_API_KEY="AIzaSy_..."
export CODEX_API_KEY="sk_..."
```

See `.env.example` and `config/promptwise_v2.yaml` for all options.
