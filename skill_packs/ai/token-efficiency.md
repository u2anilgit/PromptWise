---
name: token-efficiency
description: "Minimize token spend without losing fidelity: cache stable prefixes, compress verbose context, batch small tasks, and delegate fan-out reads so the main thread keeps the conclusion not the dump."
triggers: ["save tokens", "token efficiency", "reduce context", "cheaper prompt", "less tokens"]
depends_on: []
roles: ["Dev", "Architect"]
model_tier: "sonnet"
---

# Token Efficiency Skill

Pairs with PromptWise's plan_cache, compress_prompt, batch_prompts, and summarize_thread.

- **Cache the stable prefix.** A large system/context block reused across calls should
  carry a cache breakpoint (only above the provider's minimum cacheable length).
- **Compress verbose context.** Drop articles, filler, and restated history; keep
  code, identifiers, exact errors, and numbers verbatim.
- **Batch small tasks.** Several tiny independent prompts -> one call with a structured
  request, instead of paying per-call overhead each time.
- **Summarize for handoff.** When a thread grows long, compress it to a reset prompt
  rather than carrying the whole transcript forward.
- **Delegate fan-out reads.** When answering means sweeping many files, send a
  sub-agent and keep its conclusion — not every excerpt — in the main context.
- **Right-size the model.** Route cheap, mechanical work to a fast tier; reserve the
  powerful tier for high-stakes reasoning.
