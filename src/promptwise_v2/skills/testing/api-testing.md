---
name: api-testing
description: Generate API tests from OpenAPI spec — pytest file and Postman collection.
triggers:
  - api test
  - test api
  - integration test
  - postman collection
  - api validation
  - endpoint test
depends_on:
  - api-docs
output_schema:
  type: object
  properties:
    test_count:
      type: integer
    pytest_file:
      type: string
    postman_collection:
      type: object
  required:
    - test_count
    - pytest_file
roles:
  - Dev
model_tier: sonnet
---

# API Testing Generator

Generate API tests from OpenAPI spec (output of api-docs skill). For each endpoint: (1) success case (200/201), (2) validation error (400), (3) auth error (401), (4) not found (404 where applicable). Generate: pytest test file (using httpx/requests) + Postman collection JSON. Test data: realistic examples matching schema.

## Input

Expects OpenAPI 3.1 YAML (from `api-docs` skill output or existing spec file).

## Test Cases per Endpoint

For each `path + method` combination generate:

| # | Scenario | Expected Status |
|---|----------|----------------|
| 1 | Happy path with valid data | 200 or 201 |
| 2 | Missing required field | 400 |
| 3 | Invalid field type/format | 400 |
| 4 | No auth token | 401 |
| 5 | Invalid/expired auth token | 401 |
| 6 | Resource not found (GET/PUT/DELETE by ID) | 404 |

## pytest File Structure

```python
import pytest
import httpx

BASE_URL = "http://localhost:8000"

@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL)

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}

class TestResourceEndpoint:
    def test_get_resource_success(self, client, auth_headers):
        response = client.get("/resource/123", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    def test_get_resource_not_found(self, client, auth_headers):
        response = client.get("/resource/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_get_resource_unauthorized(self, client):
        response = client.get("/resource/123")
        assert response.status_code == 401
```

## Postman Collection Format

Generate a valid Postman Collection v2.1 JSON with:
- Collection name from OpenAPI `info.title`
- Folders per API tag/resource
- Requests with pre-request scripts for auth
- Test scripts asserting `pm.response.to.have.status(200)`

## Test Data

- Use realistic examples from OpenAPI `example` fields or `x-faker` extensions.
- Use UUIDs for ID fields, real-looking names for string fields.
- Never use production data.

## Output

Return `test_count` (integer), `pytest_file` (file path string), and `postman_collection` (Postman JSON object). Output the full pytest file content as a code block.
