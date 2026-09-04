---
name: compact-guard
description: "Preserve critical state across context compaction: externalize the task list, decisions, and open threads to durable notes so a summarized context can resume without losing work."
triggers: ["compact guard", "survive compaction", "context compaction", "don't lose state", "preserve context"]
depends_on: []
roles: ["Dev", "Architect"]
model_tier: "sonnet"
---

# Compact Guard Skill

When a long session is summarized, in-context-only state is lost. Externalize it first.

- **Externalize the work-list.** Keep the task checklist in a durable place (a tracked
  task, a notes file, the audit trace) — not only in the conversation.
- **Record decisions, not just outcomes.** Write down *why* a choice was made so a
  resumed context doesn't relitigate it.
- **Name open threads.** Before compaction, list what is in-flight and what's next, so
  the summary can carry intent forward.
- **Pin the invariants.** Constraints, file paths, and acceptance criteria belong in a
  stable artifact the next context window will reload.
- **Verify after resume.** On a fresh/summarized context, re-read the externalized
  state and confirm file/symbol references still exist before acting on them.

Pairs with summarize_thread (compress for handoff) and the hash-chained audit trace
(durable record of what changed).
