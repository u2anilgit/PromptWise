---
name: deslop
description: "Strip AI 'slop' from generated text and code: filler, hedging, restated prompts, redundant comments, and ceremony that adds tokens but no information."
triggers: ["deslop", "remove slop", "tighten output", "cut filler", "clean up the writing"]
depends_on: []
roles: ["Dev", "Writer"]
model_tier: "sonnet"
---

# Deslop Skill

Generated output drifts toward padding. Remove it without losing substance.

- **Cut filler and hedging.** Drop "it's worth noting", "basically", "in order to",
  "as an AI". Say the thing directly.
- **Don't restate the prompt.** No "Sure, here is the function you asked for." Lead
  with the answer.
- **Delete redundant comments.** A comment that re-reads the code (`# increment i`)
  is noise. Keep comments that explain *why*, not *what*.
- **Collapse ceremony.** No throat-clearing intro and summary that repeat each other.
  One of them, if either.
- **Prefer concrete to vague.** "handles errors" -> name the error and the handling.
- **Stop when done.** No "Let me know if you'd like me to..." trailer.

Preserve: technical accuracy, exact error strings, code semantics, required citations.
