---
name: brd-generator
description: Generate a Business Requirements Document (BRD) with all standard sections.
triggers:
  - brd
  - business requirements
  - business requirements document
  - stakeholder requirements
depends_on: []
output_schema:
  type: object
  properties:
    document_title:
      type: string
    sections:
      type: array
      items:
        type: object
    format:
      type: string
  required:
    - document_title
    - sections
roles:
  - PM
  - BA
model_tier: opus
---

# BRD Generator — Business Requirements Document

Generate Business Requirements Document (BRD). Sections: Executive Summary, Business Objectives, Scope (in/out), Stakeholder Analysis, Functional Requirements (numbered), Non-Functional Requirements, Assumptions, Constraints, Success Criteria. Output: structured Markdown. Also generate DOCX-compatible format hint.

## Structure

1. **Executive Summary** — one-paragraph business context, problem statement, and proposed solution.
2. **Business Objectives** — numbered list of measurable objectives tied to business value.
3. **Scope** — In Scope (explicit features/processes covered) and Out of Scope (explicit exclusions).
4. **Stakeholder Analysis** — table: Name/Group, Role, Interest, Influence (High/Medium/Low).
5. **Functional Requirements** — FR-001, FR-002… numbered requirements with description and priority.
6. **Non-Functional Requirements** — performance, security, availability, scalability, compliance.
7. **Assumptions** — list of things assumed true for this BRD to be valid.
8. **Constraints** — budget, timeline, regulatory, technical constraints.
9. **Success Criteria** — measurable KPIs and acceptance conditions.

## Output Format

Produce structured Markdown with `##` sections matching the above. Include a DOCX-compatible format hint as a comment block at the end:

```
<!-- DOCX-HINT: Use Heading1 for document title, Heading2 for each section,
     Table style "Grid Table 4 Accent 1" for stakeholder/requirements tables. -->
```

Return `document_title`, `sections` array (each with `title` and `content`), and `format: "markdown"`.
