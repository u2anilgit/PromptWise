---
name: sbom-generator
description: Generate a Software Bill of Materials (SBOM) in CycloneDX 1.5 JSON format from project lock files.
triggers:
  - sbom
  - software bill of materials
  - cyclonedx
  - inventory
  - dependency list
depends_on: []
output_schema:
  type: object
  properties:
    format:
      type: string
    component_count:
      type: integer
    sbom_json:
      type: string
  required:
    - component_count
    - sbom_json
roles:
  - Dev
  - IT
model_tier: haiku
---

# SBOM Generator

Generate Software Bill of Materials in CycloneDX 1.5 JSON format. Read lock files: requirements.txt/poetry.lock (Python), package-lock.json/yarn.lock (Node), go.sum (Go), Cargo.lock (Rust). For each component: name, version, purl, license. Output valid CycloneDX JSON.

## Lock File Sources

- **Python**: `requirements.txt` (pinned), `poetry.lock`
- **Node.js**: `package-lock.json`, `yarn.lock`
- **Go**: `go.sum`
- **Rust**: `Cargo.lock`

## Component Object Format

Each component in the CycloneDX JSON:
```json
{
  "type": "library",
  "name": "requests",
  "version": "2.31.0",
  "purl": "pkg:pypi/requests@2.31.0",
  "licenses": [{"license": {"id": "Apache-2.0"}}]
}
```

## CycloneDX 1.5 Output Structure

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "serialNumber": "urn:uuid:<generated-uuid>",
  "version": 1,
  "metadata": {"component": {"type": "application", "name": "<project-name>"}},
  "components": [...]
}
```

## purl Formats

- Python: `pkg:pypi/<name>@<version>`
- Node: `pkg:npm/<name>@<version>`
- Go: `pkg:golang/<module>@<version>`
- Rust: `pkg:cargo/<name>@<version>`

Return `sbom_json` as a serialized JSON string and `component_count` as the total number of components listed.
