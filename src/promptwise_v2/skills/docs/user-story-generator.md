---
name: user-story-generator
description: Generate user stories in standard Agile format with acceptance criteria and story points.
triggers:
  - user story
  - user stories
  - agile stories
  - story points
  - backlog item
  - acceptance criteria
depends_on: []
output_schema:
  type: object
  properties:
    stories:
      type: array
      items:
        type: object
    total_count:
      type: integer
  required:
    - stories
    - total_count
roles:
  - PM
  - SM
model_tier: haiku
---

# User Story Generator

Generate user stories in standard format: As a [role], I want [action], so that [benefit]. For each story include: {id, title, description, acceptance_criteria (array of testable conditions), story_points (Fibonacci: 1/2/3/5/8/13), priority: P1/P2/P3}. Group by epic. Cover happy path and 2 edge cases per story.

## Output Format

Group stories under epics:

```
## Epic: [Epic Name]

### US-001: [Title]
**As a** [role], **I want** [action], **so that** [benefit].

**Acceptance Criteria:**
- [ ] Given [context], when [action], then [expected outcome]
- [ ] Given [edge case], when [action], then [expected outcome]
- [ ] Given [error case], when [action], then [error handled gracefully]

**Story Points:** 3 | **Priority:** P1
```

## Story Point Guide

- 1 pt: trivial change, < 2 hours
- 2 pts: small, well-understood, < half day
- 3 pts: medium, some unknowns, ~1 day
- 5 pts: larger, notable complexity, 2-3 days
- 8 pts: complex, multiple unknowns, ~1 week
- 13 pts: very large, should be split if possible

## Priority Guide

- P1: Must have this sprint — blocks release or other stories
- P2: Should have — high value, not blocking
- P3: Nice to have — deferred to future sprint if needed

## Rules

- Each acceptance criterion is independently testable.
- Every story covers: (1) happy path, (2) boundary/edge case, (3) error case.
- Stories over 8 points must include a split suggestion.
- Return `stories` array and `total_count` integer.
