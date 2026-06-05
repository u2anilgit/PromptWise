---
name: tdd
description: Write failing tests before implementation code using the red-green-refactor cycle.
triggers:
  - tdd
  - test-driven
  - failing test
  - red-green
  - write tests first
depends_on: []
output_schema:
  type: object
  properties:
    tests_written:
      type: array
      items:
        type: string
      description: List of test function/method names written
    test_file:
      type: string
      description: Path to the test file created or modified
    coverage_target:
      type: string
      description: Target code coverage percentage or description
  required:
    - tests_written
    - test_file
    - coverage_target
roles:
  - Dev
model_tier: sonnet
---

# TDD — Test-Driven Development

Write failing tests BEFORE implementation code. Red-green-refactor cycle. Tests must specify exact expected behavior. Use pytest for Python, jest for JavaScript, go test for Go. Assert exact values, not 'truthy'. Each test one behavior.

## Process

1. **Red** — Write a failing test that describes the desired behavior. Run it and confirm it fails for the right reason.
2. **Green** — Write the minimum implementation code to make the test pass. Do not over-engineer.
3. **Refactor** — Clean up the code while keeping tests green. Improve naming, remove duplication.

## Rules

- One assertion per test where possible — each test covers exactly one behavior.
- Test names must read as specifications: `test_user_cannot_login_with_wrong_password`.
- Use exact expected values: `assert result == 42`, not `assert result`.
- Never write implementation before the test exists and fails.
- Tests must be deterministic — no random data, no time-dependent assertions without mocking.

## Framework guidance

- **Python**: use `pytest`, fixtures for setup, `pytest.raises` for exceptions.
- **JavaScript/TypeScript**: use `jest` or `vitest`, `describe`/`it` blocks, `expect(...).toBe(...)`.
- **Go**: use `testing` package, table-driven tests with `t.Run(...)`.

## Output

Return the list of test names written, the file path, and the target coverage level.
