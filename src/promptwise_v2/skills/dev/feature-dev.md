---
name: feature-dev
description: Orchestrator skill that chains tdd, implementation, code-review, and verification to deliver a complete feature.
triggers:
  - build feature
  - implement
  - add feature
  - new feature
  - develop
depends_on:
  - tdd
  - code-review
  - verification-before-completion
output_schema:
  type: object
  properties:
    implementation_files:
      type: array
      items:
        type: string
      description: List of source files created or modified during implementation
    test_files:
      type: array
      items:
        type: string
      description: List of test files created or modified
    review_summary:
      type: string
      description: Summary of code review findings and resolution
    verified:
      type: boolean
      description: Whether all verification checks passed before completion
  required:
    - implementation_files
    - test_files
    - review_summary
    - verified
roles:
  - Dev
model_tier: auto
---

# Feature Development — Orchestrator

Chains tdd → implementation → code-review → verification. Drives a feature from requirements to verified, reviewed code.

## Step 1: Requirements Clarification

Before writing any code, confirm:
- What is the exact behavior the feature must produce?
- What are the acceptance criteria?
- What are the edge cases and error conditions?
- Are there constraints (performance, security, compatibility)?

Do not proceed until requirements are unambiguous.

## Step 2: Write Failing Tests (invoke tdd)

Invoke the `tdd` skill. Write tests that specify the required behavior before any implementation exists. Confirm each test fails for the right reason.

## Step 3: Implement to Pass Tests

Write the minimum implementation code to make all tests pass.

- Do not add functionality not covered by a test.
- Follow the project's existing code style and patterns.
- Keep functions small and single-purpose.

## Step 4: Code Review (invoke code-review)

Invoke the `code-review` skill on all changed files. Address any issues rated `critical` or `high` before continuing. Document the resolution of each finding.

## Step 5: Verify (invoke verification-before-completion)

Invoke the `verification-before-completion` skill. Only proceed if `all_clear` is true.

## Output

Return: list of implementation files changed, list of test files, a summary of the code review findings and how they were resolved, and whether verification passed.
