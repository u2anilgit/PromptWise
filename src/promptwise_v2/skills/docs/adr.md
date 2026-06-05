---
name: adr
description: Create Architecture Decision Records in MADR format and commit them via git-workflow.
triggers:
  - adr
  - architecture decision record
  - decision record
  - architecture decision
  - technical decision
depends_on:
  - git-workflow
output_schema:
  type: object
  properties:
    title:
      type: string
    status:
      type: string
      enum:
        - proposed
        - accepted
        - deprecated
        - superseded
    decision:
      type: string
      description: What was decided and why
    consequences:
      type: array
      items:
        type: string
  required:
    - title
    - status
    - decision
roles:
  - Architect
model_tier: sonnet
---

# ADR — Architecture Decision Record

Create Architecture Decision Record in MADR format. Structure: Title, Date, Status (proposed/accepted), Context (forces driving decision), Decision (what was decided and why), Consequences (positive + negative + neutral). Keep concise. Store in docs/decisions/NNNN-title.md. Auto-commit via git-workflow skill.

## MADR Template

```markdown
# NNNN — [Short imperative title: "Use PostgreSQL for primary storage"]

Date: YYYY-MM-DD
Status: proposed | accepted | deprecated | superseded

## Context

[Describe the forces, constraints, and requirements that drove this decision.
Include relevant alternatives considered.]

## Decision

[State the decision clearly. Explain WHY this option was chosen over alternatives.
One paragraph max.]

## Consequences

### Positive
- [Benefit 1]
- [Benefit 2]

### Negative
- [Trade-off 1]
- [Trade-off 2]

### Neutral
- [Side effect that is neither good nor bad]
```

## Numbering Convention

Find the highest existing ADR number in `docs/decisions/` and increment by 1. Zero-pad to 4 digits: `0001`, `0002`, etc.

## File Naming

`docs/decisions/NNNN-slug-from-title.md` — lowercase, hyphens, no special chars.

## Status Transitions

- `proposed` → `accepted` once approved by tech lead or architecture board.
- `accepted` → `deprecated` when no longer relevant.
- `accepted` → `superseded` when replaced by a newer ADR (add link to superseding ADR).

## Commit

After writing the file, invoke git-workflow skill to commit:
```
docs(adr): add ADR-NNNN [title]
```

Return `title`, `status`, `decision` (one-paragraph summary), and `consequences` array.
