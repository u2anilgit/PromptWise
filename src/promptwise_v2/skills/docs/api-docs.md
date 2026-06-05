---
name: api-docs
description: Generate OpenAPI 3.1 YAML documentation from code or route definitions.
triggers:
  - api docs
  - openapi
  - swagger
  - api documentation
  - rest api docs
  - api spec
depends_on: []
output_schema:
  type: object
  properties:
    openapi_version:
      type: string
    paths:
      type: integer
      description: Number of API paths documented
    schemas:
      type: integer
      description: Number of component schemas
    openapi_yaml:
      type: string
      description: Complete OpenAPI 3.1 YAML document
  required:
    - openapi_yaml
    - paths
roles:
  - Dev
model_tier: sonnet
---

# API Documentation Generator — OpenAPI 3.1

Generate OpenAPI 3.1 YAML documentation. Analyze code/routes to extract: endpoints (path, method, params), request/response schemas, authentication, error codes. Output valid OpenAPI 3.1 YAML with: info, servers, paths, components/schemas. Each endpoint: summary, description, parameters, requestBody, responses with examples.

## Analysis Steps

1. Scan route definitions (FastAPI decorators, Flask routes, Express router, Django urls.py).
2. Extract path parameters, query parameters, and request body schemas.
3. Infer response schemas from Pydantic models, TypeScript interfaces, or return type annotations.
4. Detect authentication scheme (Bearer JWT, API key, OAuth2, Basic).

## OpenAPI 3.1 Template

```yaml
openapi: "3.1.0"
info:
  title: "API Name"
  version: "1.0.0"
  description: "API description"
servers:
  - url: "https://api.example.com/v1"
    description: "Production"
  - url: "http://localhost:8000"
    description: "Development"
paths:
  /resource/{id}:
    get:
      summary: "Get resource by ID"
      description: "Returns a single resource"
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: "Success"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Resource"
              example:
                id: "abc123"
                name: "Example"
        "404":
          $ref: "#/components/responses/NotFound"
        "401":
          $ref: "#/components/responses/Unauthorized"
components:
  schemas:
    Resource:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
      required: [id, name]
  responses:
    NotFound:
      description: "Resource not found"
    Unauthorized:
      description: "Missing or invalid authentication"
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
security:
  - BearerAuth: []
```

## Rules

- Every path must have at least 200/201 and 400/401 responses defined.
- All schemas use `$ref` for reuse — no inline duplication.
- Include realistic examples for each request/response.
- Output valid YAML (validate mentally before returning).

## Output

Return `openapi_yaml` (full YAML string), `paths` count (integer), `schemas` count (integer), and `openapi_version: "3.1.0"`.
