---
name: finishing-branch
description: Pre-merge gate that runs code-review, verification-before-completion, and git-workflow before setting ready_to_merge.
triggers:
  - finish branch
  - ready to merge
  - pre-merge
  - complete feature
  - ship it
depends_on:
  - code-review
  - verification-before-completion
  - git-workflow
output_schema:
  type: object
  properties:
    review_passed:
      type: boolean
      description: Whether code-review returned approved=true (score >= 80, no critical issues)
    tests_pass:
      type: boolean
      description: Whether all verification checks passed including the test suite
    commit_message:
      type: string
      description: Final Conventional Commits formatted commit message for the merge
    ready_to_merge:
      type: boolean
      description: Whether all three gates passed and the branch is safe to merge
  required:
    - review_passed
    - tests_pass
    - commit_message
    - ready_to_merge
roles:
  - Dev
model_tier: sonnet
---

# Finishing a Branch — Pre-Merge Gate

Pre-merge gate. Runs: code-review → verification-before-completion → git-workflow. Gate: review score >=80 AND all verification checks pass AND commit follows conventional commits. Only set ready_to_merge=true if all three gates pass.

## Gate 1: Code Review (invoke code-review)

Invoke the `code-review` skill on all files changed in this branch.

- **Pass condition**: `approved: true` (score ≥80 AND no critical issues).
- **Fail condition**: any critical issue exists OR score <80.
- If Gate 1 fails: stop, report the blocking issues, do not proceed to Gate 2.

## Gate 2: Verification (invoke verification-before-completion)

Invoke the `verification-before-completion` skill.

- **Pass condition**: `all_clear: true` (tests pass, no TODOs, docs updated, security clean).
- **Fail condition**: any single check is false.
- If Gate 2 fails: stop, report which checks failed, do not proceed to Gate 3.

## Gate 3: Git Hygiene (invoke git-workflow)

Invoke the `git-workflow` skill to generate the final commit message.

- **Pass condition**: commit message follows Conventional Commits format, subject ≤50 chars, imperative mood.
- **Fail condition**: commit message does not meet the format.

## Final Decision

Set `ready_to_merge: true` only when ALL three gates pass:
- `review_passed: true` (Gate 1)
- `tests_pass: true` (Gate 2, `all_clear`)
- Commit message is valid (Gate 3)

If any gate fails, `ready_to_merge` must be `false`. Report which gate failed and what must be fixed.

## Rules

- Do not rationalize failures or grant exceptions.
- Do not set `ready_to_merge: true` if you are uncertain about any gate.
- Document the result of each gate in the response even when all pass.
