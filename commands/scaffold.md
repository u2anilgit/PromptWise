---
description: Classify a request (new build / re-engineer / re-architect / diagram), propose approach options, and emit an interactive spec page + a diagram via PromptWise.
argument-hint: [what you want to build / change / diagram]
---

Scaffold a solution for the request below. Run `python -m promptwise scaffold "<the request>"`
to classify the shape of work, propose 2-4 concrete approach options with trade-offs, and
generate a self-contained interactive spec page plus a validated diagram.

Then present the options to the user with a short recommendation (which one, and why, given
their context), and offer to open the generated page or refine the diagram. If the request is
about visualizing something, focus on the diagram; if it is about building or re-architecting,
lead with the options and the trade-offs.

$ARGUMENTS
