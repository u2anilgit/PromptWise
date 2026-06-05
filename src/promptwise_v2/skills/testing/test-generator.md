---
name: test-generator
description: Generate test suites using AAA pattern for Python, JavaScript, or Go code.
triggers:
  - generate tests
  - write tests
  - create tests
  - test cases
  - unit tests
  - test suite
depends_on:
  - tdd
output_schema:
  type: object
  properties:
    test_file:
      type: string
    test_count:
      type: integer
    framework:
      type: string
    tests:
      type: array
      items:
        type: object
  required:
    - test_file
    - test_count
    - framework
roles:
  - Dev
model_tier: sonnet
---

# Test Generator

Generate test suite for given code. Auto-detect framework: pytest (Python), jest (JavaScript/TypeScript), go test (Go). Pattern: Arrange-Act-Assert (AAA). For each function/method: test happy path + boundary conditions + error cases. Mock external dependencies. Each test: {name, arrange, act, assert_description}. Name tests: test_[function]_[scenario].

## Framework Detection

- **Python** → `pytest` if `*.py` files; use fixtures, `pytest.raises`, `unittest.mock.patch`.
- **JavaScript/TypeScript** → `jest` if `package.json` has jest; `vitest` if vitest config found.
- **Go** → `testing` package; table-driven tests with `t.Run(...)`.

## AAA Pattern

```python
def test_function_scenario():
    # Arrange
    input_data = ...
    expected = ...

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected
```

## Test Coverage per Function

For each function/method generate:
1. **Happy path** — normal inputs, expected output.
2. **Boundary conditions** — empty string, zero, max value, None/null.
3. **Error case** — invalid input triggers expected exception/error.

## Naming Convention

- Python: `test_[function_name]_[scenario]` — e.g., `test_parse_date_valid_iso_format`
- JavaScript: `describe('[ClassName]') > it('[method] [scenario]')`
- Go: `TestFunctionName_Scenario`

## Mocking

- Mock all I/O: database calls, HTTP requests, file system, time.
- Python: `unittest.mock.patch` or `pytest-mock`'s `mocker.patch`.
- JavaScript: `jest.mock()` or `vi.mock()`.
- Go: interfaces + test doubles.

## Test Object Format

Each test in output array:
```json
{
  "name": "test_parse_date_valid_iso_format",
  "arrange": "input_date = '2026-06-05'",
  "act": "result = parse_date(input_date)",
  "assert_description": "returns datetime(2026, 6, 5) with no error"
}
```

## Output

Return `test_file` (path), `test_count` (integer), `framework` (string), and `tests` array. Also output the full test file content as a code block.
