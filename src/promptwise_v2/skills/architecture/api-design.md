---
name: api-design
description: Design API surface for REST, GraphQL, or gRPC with auth, versioning, and rate limiting.
triggers:
  - api design
  - rest api
  - graphql
  - api versioning
  - openapi design
  - api contract
depends_on: []
output_schema:
  type: object
  properties:
    api_style:
      type: string
      enum: [REST, GraphQL, gRPC]
    endpoints:
      type: array
      items:
        type: object
    auth_strategy:
      type: string
    versioning_strategy:
      type: string
    rate_limiting:
      type: object
  required:
    - api_style
    - endpoints
    - auth_strategy
roles:
  - Architect
  - Dev
model_tier: sonnet
---

# API Design

Design API surface. For REST: resource-oriented URLs (/resources/{id}), HTTP verbs (GET/POST/PUT/PATCH/DELETE), status codes (200/201/400/401/403/404/409/422/500). For GraphQL: schema-first, queries/mutations/subscriptions, pagination (cursor-based). Versioning: URL path (/v1/) or header. Auth: JWT Bearer or API key. Rate limiting: per-client, configurable. Output: endpoint list + OpenAPI snippet.

## REST Design Rules

- Use resource-oriented URLs: `/resources/{id}`, `/resources/{id}/sub-resources`
- HTTP verbs: GET (read), POST (create), PUT (full update), PATCH (partial update), DELETE (remove)
- Status codes: 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity, 500 Internal Server Error
- Request/response bodies: JSON with camelCase keys
- Pagination: `?page=1&limit=20` or cursor-based `?after=<cursor>&limit=20`

## GraphQL Design Rules

- Schema-first approach: define types before implementation
- Queries for reads, Mutations for writes, Subscriptions for real-time
- Pagination: cursor-based (Relay spec) — `{ edges { node cursor } pageInfo { hasNextPage endCursor } }`
- Input types for mutations; never reuse query types as inputs
- Errors: use union types or `errors` array, not HTTP status codes

## Versioning Strategy

- URL path versioning: `/v1/`, `/v2/` — most explicit, easiest to cache
- Header versioning: `Accept: application/vnd.api+json;version=2` — cleaner URLs
- Deprecation: mark old versions with `Deprecation` header, 6-month sunset window

## Auth Strategy

- JWT Bearer: `Authorization: Bearer <token>` — stateless, embeds claims
- API Key: `X-API-Key: <key>` — simple for server-to-server
- OAuth 2.0: for third-party delegated access (authorization code or client credentials flow)

## Rate Limiting

- Per-client limits: track by API key or IP
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Response on exceeded: `429 Too Many Requests` with `Retry-After` header
- Configurable tiers: free/pro/enterprise with different limits

## Output

Return endpoint list with method/path/description/request-body/response-body, chosen auth strategy, versioning approach, rate limit config, and an OpenAPI 3.0 snippet for the core endpoints.
