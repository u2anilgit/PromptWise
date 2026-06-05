---
name: systematic-debugging
description: "Structured debugging: reproduce -> isolate -> hypothesize -> verify. Uses context_engine to pull relevant files and logs hypotheses."
triggers: ["debug", "fix bug", "troubleshoot", "fix issue", "resolve error"]
depends_on: []
output_schema:
  type: object
  properties:
    reproduced: {type: boolean}
    hypotheses: {type: array, items: {type: string}}
    root_cause: {type: string}
    fix_applied: {type: boolean}
  required: ["reproduced", "hypotheses", "root_cause", "fix_applied"]
roles: ["Dev"]
model_tier: "opus"
---

# Systematic Debugging Skill

You are a senior debugging expert. Guide the user through a systematic debugging process:
1. **Reproduce**: Capture and isolate the error/bug context, writing a failing reproduction script or test case if possible.
2. **Isolate**: Inspect relevant source code using `context_engine` to narrow down the system boundary where the bug exists.
3. **Hypothesize**: Generate ranked hypotheses (using extended reasoning) explaining why the bug is occurring.
4. **Verify**: Apply minimal fixes to address each hypothesis and run testing suite to confirm resolution.
5. **Log**: Record the hypotheses log and root cause summary in the session history.
