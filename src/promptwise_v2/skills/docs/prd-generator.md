---
name: prd-generator
description: Generate a Product Requirements Document (PRD) with user stories and acceptance criteria.
triggers:
  - prd
  - product requirements
  - product spec
  - feature spec
  - product requirements document
depends_on: []
output_schema:
  type: object
  properties:
    product_name:
      type: string
    user_stories:
      type: array
      items:
        type: object
    acceptance_criteria:
      type: array
      items:
        type: string
    out_of_scope:
      type: array
      items:
        type: string
  required:
    - product_name
    - user_stories
roles:
  - PM
model_tier: sonnet
---

# PRD Generator — Product Requirements Document

Generate Product Requirements Document. Format: as [role] I want [feature] so that [benefit]. Include: product vision, user personas, user stories with acceptance criteria, out-of-scope items, success metrics, timeline. Each user story: {role, want, benefit, acceptance_criteria[], priority: high/medium/low}.

## Structure

### Product Vision
One sentence: "For [target user] who [need], [product name] is a [category] that [key benefit]. Unlike [alternative], our product [differentiator]."

### User Personas
For each persona: name, role/title, goals, pain points, technical level.

### User Stories
Each story follows: **As a** [role], **I want** [action], **so that** [benefit].

Each story object:
```json
{
  "id": "US-001",
  "title": "short title",
  "role": "persona role",
  "want": "action/feature description",
  "benefit": "business/user value",
  "acceptance_criteria": ["Given...When...Then...", "..."],
  "priority": "high | medium | low",
  "story_points": 3
}
```

### Out of Scope
Explicit list of features/behaviors excluded from this version.

### Success Metrics
Measurable KPIs: adoption rate, task completion time, error rate, NPS.

### Timeline
Milestones with target dates and owning team.

## Rules

- Every acceptance criterion must be testable.
- Priority: high = must-have (MVP), medium = should-have, low = nice-to-have.
- Cover at least one edge-case or error-handling story per feature area.
