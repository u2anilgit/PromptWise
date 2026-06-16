---
name: api-docs
description: "Parses code routes and generates OpenAPI 3.1 YAML specs."
triggers: ["api docs", "generate openapi", "openapi", "swagger", "document api", "generate swagger"]
depends_on: []
output_schema:
  type: object
  properties:
    openapi_yaml: {type: string}
    endpoints: {type: array, items: {type: string}}
  required: ["openapi_yaml", "endpoints"]
roles: ["Dev"]
model_tier: "sonnet"
---

# API Documentation Skill

You are an API design expert. Create comprehensive route documentation:
1. **Analyze**: Scan endpoint definitions, routes, headers, and payload parameters.
2. **OpenAPI**: Draft a valid, production-ready OpenAPI 3.1 schema representation in YAML.
3. **Format**: List all mapped endpoints, methods, and expected JSON structures.
