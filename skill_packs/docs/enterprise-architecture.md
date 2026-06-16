---
name: enterprise-architecture
description: "Guided enterprise-architecture templates (TOGAF ADM, Zachman, ArchiMate layers, C4) as knowledge/templates — capability maps, ADRs, NFR matrices. Methodology guidance, not a third-party tool integration."
triggers: ["enterprise architecture", "togaf", "zachman", "archimate", "capability map", "ea framework", "reference architecture"]
depends_on: ["solution-architecture", "architecture-diagram"]
output_schema:
  type: object
  properties:
    framework: {type: string}
    artifact: {type: string}
  required: ["framework", "artifact"]
roles: ["Architect", "C-Suite"]
model_tier: "opus"
---

# Enterprise Architecture Skill

Provide EA guidance using established **frameworks as templates** — these are
methodologies/notations, not external software. Produce the smallest useful artifact, not
a full framework rollout.

1. Pick the lens that fits the ask (don't apply all):
   - **TOGAF ADM** — phases A–H. Most asks need just one: Vision (A), Business/Data/App/
     Tech architecture (B–D), or a capability/gap analysis. Produce that phase's artifact,
     not the whole ADM.
   - **Zachman** — a 6×6 classification grid (What/How/Where/Who/When/Why × perspectives).
     Use to check coverage; fill only the relevant cells.
   - **ArchiMate** — Business / Application / Technology layers. Describe elements per layer
     and the relationships between layers.
   - **C4** — for the concrete software view; delegate to `solution-architecture`.
2. Common deliverables (pick one): capability map, current→target state + gap analysis,
   NFR/quality-attribute matrix, principles & standards list, ADR set.
3. Render structure as Mermaid via the `architecture-diagram` pack where a picture helps.
4. Keep it vendor-neutral and right-sized. Flag when a lighter approach
   (`solution-architecture`) is enough and EA framing is overkill.
