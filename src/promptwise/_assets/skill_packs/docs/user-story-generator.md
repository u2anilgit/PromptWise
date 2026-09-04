---
name: user-story-generator
description: "Bulk user story generator with acceptance criteria in Gherkin or plain English."
triggers: ["generate user stories", "user stories", "write stories"]
depends_on: []
output_schema:
  type: object
  properties:
    stories:
      type: array
      items:
        type: object
        properties:
          story: {type: string}
          acceptance_criteria: {type: array, items: {type: string}}
        required: ["story", "acceptance_criteria"]
  required: ["stories"]
roles: ["PM", "SM"]
model_tier: "haiku"
---

# User Story Generator Skill

Given a feature description, generate Agile User Stories in the standard format:
"As a [role], I want [action] so that [benefit]."
For each story, define 3+ explicit Acceptance Criteria (Given/When/Then or bullet points).
