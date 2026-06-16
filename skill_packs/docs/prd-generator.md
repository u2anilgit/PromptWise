---
name: prd-generator
description: "Product requirements document generator with embedded user stories, success metrics, and feature breakdown."
triggers: ["generate prd", "prd", "product requirements", "write prd"]
depends_on: ["user-story-generator"]
output_schema:
  type: object
  properties:
    prd_markdown: {type: string}
    stories: {type: array, items: {type: object}}
    success_metrics: {type: array, items: {type: string}}
  required: ["prd_markdown", "stories", "success_metrics"]
roles: ["PM"]
model_tier: "opus"
---

# PRD Generator Skill

You are a product management leader. Produce a high-quality Product Requirements Document (PRD) detailing:
- Executive Summary & Goals
- Target Personas
- Key Features & Scope
- Embedded User Stories
- Success Metrics & KPIs
- Technical Constraints
