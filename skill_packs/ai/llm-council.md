---
name: llm-council
description: "Stakes-aware multi-model deliberation: convene several models/personas, gather independent positions, then synthesize a decision with dissent recorded."
triggers: ["llm council", "second opinion", "multi model decision", "deliberate", "stakes aware", "model panel"]
depends_on: []
roles: ["Dev", "Architect", "PM"]
model_tier: "opus"
---

# LLM Council Skill

Use when a decision is high-stakes or contested and a single model's answer is not
enough. Routing picks a model; the council decides *what is right*.

1. **Frame the question.** State the decision, the options, and the success criteria
   in one paragraph. Note the stakes (low / medium / high) — this sets how many
   independent positions to gather.
2. **Convene independent positions.** Ask N distinct lenses (e.g. risk-first,
   user-first, cost-first; or different model tiers) for a position *and its strongest
   counter-argument*. Keep them blind to each other to avoid anchoring.
3. **Score against the criteria.** Rate each position on the stated success criteria,
   not on confidence or eloquence.
4. **Synthesize.** Adopt the strongest position; graft the best ideas from the
   runners-up. **Record the dissent** — the rejected arguments are part of the trace.
5. **Escalate to a human** when the council splits on a high-stakes call rather than
   forcing a majority.
