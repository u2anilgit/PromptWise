---
name: thoroughness
description: "Exhaustive-coverage discipline: enumerate the full work-list before acting, track what's done vs pending, and surface anything dropped instead of silently truncating."
triggers: ["be thorough", "exhaustive", "cover everything", "complete coverage", "don't miss anything"]
depends_on: []
roles: ["Dev", "QA", "Analyst"]
model_tier: "opus"
---

# Thoroughness Skill

For audits, migrations, and "find all X" tasks where missing one item is the failure.

1. **Enumerate first.** Build the complete work-list (files, cases, endpoints) before
   touching any single item. A task you can't enumerate, you can't complete.
2. **Track done vs pending.** Keep an explicit checklist. Mark each item only when it
   is actually finished and verified.
3. **Multi-angle sweep.** When one search won't find everything, search by container,
   by content, by entity, and by time — each blind to the others.
4. **No silent truncation.** If you cap coverage (top-N, sampling, skipped a hard
   case), say so explicitly. Silent limits read as "covered everything" when they
   aren't.
5. **Completeness pass.** Before claiming done, ask: what modality didn't I run, what
   claim is unverified, what item is still pending? That answer is the next round.
