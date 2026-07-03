---
description: Run a durable eval + regression suite (prompt+rubric cases) offline and gate on drift via PromptWise.
argument-hint: [suite path or case description]
---

Use the PromptWise `run_eval_harness` tool to run the eval suite below. An eval case is a prompt plus a rubric (`expect_contains` / `expect_absent`, optional `min_score`, `task_class`, `tier`). Pass cases inline via `cases` or point at a local JSON file/dir via `cases_path` (e.g. `config/eval_suite.json`).

The harness runs fully offline by default (a record/dry-run mode that never calls the cloud; a local on-device runtime is used only when one is available), scores each output with the existing quality gate, diffs the result against the stored per-tier baseline to flag regressions, and returns a `pass`/`fail` gate. Every scored case is also written back into the adaptive-routing outcome store, so routing learns from eval results.

Report the gate, the met/not-met counts, and — for any regression — the case id, tier, and how it drifted (verdict flip or score drop vs. baseline). To bless the current run as the new baseline (after a deliberate, reviewed change), pass `save_baseline: true`.

$ARGUMENTS
