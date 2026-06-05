---
name: test-coverage-advisor
description: Analyze test coverage reports and prioritize gaps by cyclomatic complexity.
triggers:
  - test coverage
  - coverage report
  - missing tests
  - coverage gaps
  - improve coverage
  - lcov
depends_on:
  - test-generator
output_schema:
  type: object
  properties:
    current_coverage_pct:
      type: number
    gaps:
      type: array
      items:
        type: object
    priority_order:
      type: array
      items:
        type: string
  required:
    - gaps
    - priority_order
roles:
  - Dev
model_tier: haiku
---

# Test Coverage Advisor

Analyze test coverage and prioritize gaps. Read: coverage.xml (pytest), lcov.info (jest), cover.out (go). Rank uncovered code by cyclomatic complexity (higher complexity = higher priority to test). For each gap: {file, function, complexity_score, lines_uncovered}. Chain to test-generator for top 3 gaps. Target: 80% line coverage minimum.

## Coverage File Formats

- **Python/pytest**: `coverage.xml` (Cobertura format) or `.coverage` file.
  - Run: `pytest --cov=src --cov-report=xml`
- **JavaScript/jest**: `lcov.info` in `coverage/` directory.
  - Run: `jest --coverage`
- **Go**: `cover.out` file.
  - Run: `go test ./... -coverprofile=cover.out`

## Gap Analysis

For each uncovered function/block:
```json
{
  "file": "src/module/service.py",
  "function": "process_payment",
  "complexity_score": 12,
  "lines_uncovered": 45,
  "branch_coverage_pct": 30.0
}
```

## Complexity Scoring

Cyclomatic complexity (CC):
- 1-5: simple → low priority
- 6-10: moderate → medium priority
- 11-20: complex → high priority
- 21+: very complex → critical priority (also flag for refactoring)

## Priority Ordering

Sort gaps by: `complexity_score DESC, lines_uncovered DESC`.

Output `priority_order` as ordered list of `"file::function"` strings.

## Action: Chain to test-generator

For the top 3 gaps, automatically invoke the `test-generator` skill with the function source code. This fills the highest-risk coverage gaps first.

## Target Thresholds

| Metric | Minimum | Target |
|--------|---------|--------|
| Line coverage | 70% | 80% |
| Branch coverage | 60% | 75% |
| Function coverage | 75% | 90% |

## Output

Return `current_coverage_pct` (number), `gaps` array sorted by priority, and `priority_order` array (top 10 as `"file::function"` strings). Include a summary section listing functions that exceed CC 20 (refactor candidates).
