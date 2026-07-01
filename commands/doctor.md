---
description: Health-check the PromptWise plugin (hooks, DB, modules, policy, registry).
argument-hint: 
---

Run the PromptWise health check by executing `python -m promptwise doctor` and report the result. It verifies hooks are registered, the state dir is writable, core modules import, policy is present, and the model registry loads. If anything reports FAIL, explain the fix (for example run `python -m promptwise bootstrap`).

$ARGUMENTS
