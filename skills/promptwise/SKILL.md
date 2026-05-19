---
name: promptwise
description: Use PromptWise when the user wants to optimize prompt cost, route requests to the right Claude model tier, plan prompt caching for repeated calls, rewrite verbose prompts, compress large context, batch small tasks, or summarize long conversations for handoff. Trigger especially for "which model should I use", "how can I save tokens", "this prompt is too long", "cache this for repeated calls", "compress this context", explicit cost questions, or any time the user pastes a large doc.
---

# PromptWise — Token & Cost Optimization Plugin

When the user invokes `/promptwise` with no subcommand, display this menu first:

```
PromptWise v1.2.0 — Available commands:

  /promptwise:route_request          Pick the right model (Haiku/Sonnet/Opus) for your task
  /promptwise:rewrite_prompt         Strip filler, tighten prompt, add role framing
  /promptwise:optimize_context       Compress large context to fit a token budget
  /promptwise:plan_cache             Design prompt-cache breakpoints for repeated calls
  /promptwise:batch_prompts          Merge 2–5 small tasks into one efficient prompt
  /promptwise:summarize_thread       Compress long conversation for a fresh thread handoff
  /promptwise:get_session_stats      Show cost, savings, cache hit rate for this session
  /promptwise:compare_providers      Compare cost across Claude / OpenAI / Gemini tiers
  /promptwise:reload_config          Hot-reload pricing.yaml / providers.yaml / roles.yaml

  — Session Timeout —
  /promptwise:ping_session           Record user activity (reset idle clock)
  /promptwise:check_session_timeout  Check if session is active/warn/expired

  — Data Management —
  /promptwise:clear_history          Delete records older than N days (data retention)
  /promptwise:export_stats           Export usage history as JSON or CSV

Usage: describe your need and PromptWise selects the right tool automatically,
       or invoke a specific subcommand directly.
```

Then ask: "What would you like to optimize?"

# When to invoke PromptWise tools

## route_request – pick the right model

Use when:
- User asks "which model should I use" / "is this an Opus task" / "can Haiku do this"
- User mentions a budget concern ("I'm spending too much on Opus")
- About to send a large or complex prompt and the right tier isn't obvious
- User specifies stakes ("this is for production", "just a quick test")

Call with:
- `text`: the prompt or task description
- `intent`: auto (default)
- `stakes`: auto (default)
- `monthly_budget_usd` and `days_elapsed_in_month`: include if user has a budget

## plan_cache – design caching for repeated calls

Use when:
- User is building an agentic loop, RAG app, or chatbot
- User mentions sending the same system prompt or document many times
- User asks "how do I reduce input cost"
- A multi-turn conversation has >5K tokens of stable history

Call with:
- `messages`: list with role, content, and optional label hints
- `expected_reuse_count`: 2 (default) or higher if user mentions volume

## rewrite_prompt – tighten a verbose prompt

Use when:
- User pastes a prompt with filler ("could you please", "I was wondering if")
- User asks to "make this shorter" or "tighten this"
- User asks for role-specific framing

Call with:
- `text`: the original prompt
- `role`: developer/analyst/writer/manager/researcher/designer/general

## optimize_context – fit context into a token budget

Use when:
- User pastes a long document
- User says "this is too long" / "compress this"
- Context clearly exceeds reasonable budget

Call with:
- `context`: the full text
- `token_budget`: 2000 (default)

## batch_prompts – merge 2–5 small tasks

Use when:
- User has multiple related small tasks
- User says "I also need to..." with follow-up tasks
- About to send 3+ similar requests

Call with:
- `tasks`: array of 2–5 task strings
- `role`: match the dominant role

## summarize_thread – handoff to a fresh chat

Use when:
- Conversation approaching context limits
- User says "summarize what we've covered" / "start fresh"
- Long debugging or design session is wrapping up

Call with:
- `conversation`: relevant prior turns
- `max_tokens`: 500 (default)

## get_session_stats – accounting

Use when:
- User asks how much they've spent/saved
- User asks about cache hit rate or model distribution
- Periodic cost check-ins

Call with:
- `since`: optional ISO timestamp filter

## compare_providers – cross-provider cost comparison

Use when:
- User asks "is this cheaper on GPT?" / "how does Gemini compare?"
- User wants to pick cheapest model for a task
- User mentions multi-provider or cost-sensitive workload

Call with:
- `text`: the prompt or task description
- `model`: model for token counting (default: claude-sonnet-4-6)

## reload_config – refresh YAML files without restart

Use when:
- User has updated pricing.yaml, providers.yaml, or roles.yaml
- User asks to "reload config" or "refresh pricing"

## ping_session – record user activity

Use when:
- Starting a new session (no session_id yet)
- User sends any message (to reset idle clock)
- Implementing session continuity across turns

Call with:
- `session_id`: omit to create new session; pass existing ID to update

Returns: `{session_id, started_ts, last_ping_ts, is_new}`

Workflow: call once per user message; store returned `session_id` for the conversation.

## check_session_timeout – detect idle sessions

Use when:
- User appears unresponsive for an extended period
- Checking before a long tool chain to confirm user is present

Call with:
- `session_id`: required — from prior `ping_session`
- `idle_threshold_minutes`: default from config (30); override per-call
- `warn_threshold_minutes`: default from config (20); override per-call

Returns: `{status, idle_minutes, recommended_action, message}`

Action on status:
- `active` → continue normally
- `warn` → surface `message` to user ("Still there? Session closes in X min.")
- `expired` → call `summarize_thread`, then suggest `/clear`

## clear_history – data retention

Use when:
- User asks to delete old records
- Implementing a retention policy ("keep 90 days")

Call with:
- `older_than_days`: required (minimum 1) — deletes records with `ts` older than N days

Returns: `{deleted_count, older_than_days}`

## export_stats – usage reporting

Use when:
- User wants a cost breakdown for their team / FinOps report
- Exporting to a spreadsheet
- Debugging unexpected cost spikes

Call with:
- `format`: "json" (default) or "csv"
- `since`: ISO 8601 timestamp to filter (optional)

Returns: JSON array or CSV string of all matching history records (all columns including `project`, `team`, `duration_ms`).
