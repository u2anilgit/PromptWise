---
name: systematic-debugging
description: "Reproduce, isolate, and fix bugs using structured hypothesis-driven debugging with extended thinking (extended_thinking_tokens: 8000)."
triggers:
  - debug
  - bug
  - crash
  - error
  - not working
  - broken
  - trace
  - stacktrace
depends_on: []
output_schema:
  type: object
  properties:
    root_cause:
      type: string
      description: Exact root cause of the bug with supporting evidence
    hypothesis:
      type: string
      description: The single hypothesis that was tested and confirmed
    fix:
      type: string
      description: The exact fix applied or recommended
    verified:
      type: boolean
      description: Whether the fix was verified to resolve the issue
  required:
    - root_cause
    - hypothesis
    - fix
    - verified
roles:
  - Dev
model_tier: opus
---

# Systematic Debugging

Reproduce → isolate → hypothesize → verify. Never guess — trace execution. Output exact root cause with evidence.

## Step 1: Reproduce

Confirm the exact failure. Obtain the full error message, stack trace, and the conditions under which it occurs. If you cannot reproduce it, you cannot debug it.

- What is the exact error message or unexpected output?
- What inputs trigger it? Always? Only sometimes?
- What environment (OS, runtime version, dependencies)?

## Step 2: Isolate

Reduce to the minimum reproducing case. Strip away everything not needed to trigger the bug.

- Can you reproduce in a fresh file with 10 lines of code?
- Which component, function, or module is the last known-good boundary?
- Binary-search the call stack: does the bug appear before or after a given call?

## Step 3: Hypothesize

Form a single, falsifiable hypothesis about the root cause.

- State it precisely: "I believe the bug is caused by X because Y."
- Do not hold multiple competing hypotheses — pick the most likely one and test it first.
- Identify what evidence would confirm or refute it.

## Step 4: Verify

Test the hypothesis by changing exactly one thing.

- If the hypothesis is correct, the change should fix the bug.
- If the test still fails, discard the hypothesis and return to Step 3.
- Document what you changed and the observed result.

## Rules

- Never guess or assume — every claim must be backed by observed behavior.
- Do not fix symptoms; find and fix the root cause.
- If a fix works but you don't understand why, keep investigating.
- Log every hypothesis tried and its result.

## Output

Return: the exact root cause with evidence, the confirmed hypothesis, the fix, and whether it was verified.
