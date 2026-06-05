---
name: refactoring
description: Safe refactoring using characterization tests to lock behavior before restructuring code.
triggers:
  - refactor
  - clean up
  - improve code
  - restructure
  - tech debt
depends_on: []
output_schema:
  type: object
  properties:
    characterization_tests:
      type: array
      items:
        type: string
      description: List of characterization test names written to lock current behavior
    changes:
      type: array
      items:
        type: string
      description: List of refactoring changes applied (one concern at a time)
    test_coverage_delta:
      type: string
      description: Change in test coverage after refactoring (e.g. "+3%" or "unchanged")
  required:
    - characterization_tests
    - changes
    - test_coverage_delta
roles:
  - Dev
model_tier: sonnet
---

# Safe Refactoring

Safe refactoring process. Never change behavior and structure simultaneously.

## Step 1: Write Characterization Tests

Before touching any code, write tests that document the current behavior — even if that behavior is surprising or wrong. These tests are your safety net.

- Run the code with representative inputs and capture the actual outputs.
- Write tests that assert those exact outputs.
- If the code is untestable, make it testable first (extract dependencies, add interfaces).
- Confirm all characterization tests pass against the unmodified code.

## Step 2: Refactor One Concern at a Time

Apply one refactoring move at a time. After each move, run the full test suite.

Allowed moves (one at a time):
- **Extract function/method**: move a cohesive block into a named function.
- **Rename**: rename a variable, function, or class to better describe its purpose.
- **Simplify condition**: replace complex boolean logic with a named predicate.
- **Remove duplication**: extract repeated code into a shared function.
- **Move responsibility**: shift a concern to the correct class or module.

## Step 3: Verify After Each Change

After every single refactoring move:
1. Run the full test suite.
2. If any test fails, revert the last change immediately — do not accumulate failures.
3. Only proceed to the next move when all tests are green.

## Rules

- **Never** change observable behavior and structure in the same commit.
- **Never** rename AND restructure in the same step.
- **Never** optimize performance during a refactoring pass — that is a separate concern.
- If you discover a bug while refactoring, record it but do not fix it during the refactor. Fix it in a separate commit after.

## Output

Return the list of characterization test names written, the list of changes applied, and the test coverage delta.
