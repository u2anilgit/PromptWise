---
name: prompt-registry
description: Manage a reusable prompt library — save, find, and list prompts by name, tags, and version.
triggers:
  - save prompt
  - find prompt
  - search prompts
  - prompt library
  - prompt registry
  - reuse prompt
depends_on: []
output_schema:
  type: object
  properties:
    action:
      type: string
      enum:
        - saved
        - found
        - listed
    prompt_id:
      type: string
    results:
      type: array
      items:
        type: object
  required:
    - action
roles:
  - Dev
  - PM
  - IT
model_tier: haiku
---

# Prompt Registry

Manage a shared prompt library. Supports save, find, and list operations.

## Operations

### Save
Store a prompt with name, tags, and version.
- Assign a stable `prompt_id` (slug of name + version, e.g. `summarize-email-v2`).
- Accept optional `tags` array (e.g. `["summarization", "email", "haiku"]`).
- Auto-increment version if a prompt with the same name already exists (v1 → v2).
- Return `action: saved` and the assigned `prompt_id`.

### Find
Semantic or keyword search for existing prompts.
- Match against name, description, and tags.
- Rank by relevance score descending.
- Return `action: found` and `results` array. Each result: `{prompt_id, name, description, tags, version, created_at}`.

### List
Return all prompts, with optional filters.
- Filter by `role` (Dev/PM/IT), `tag`, or `model_tier`.
- Sort by `created_at` descending by default.
- Return `action: listed` and `results` array.

## Versioning

- Every save creates an immutable version entry.
- Latest version is marked `is_latest: true`.
- Callers may pin to a specific version via `prompt_id` with version suffix.

## Tagging

Use tags to group prompts for reuse:
- Domain tags: `summarization`, `code-review`, `translation`, `extraction`
- Tier tags: `haiku`, `sonnet`, `opus`
- Role tags: `dev`, `pm`, `it`

## Output

Return `prompt_id` on save. Return `results` array on find or list. Always set `action`.
