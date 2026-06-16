---
name: code-optimizer
description: "Performance optimization advisor — find and fix algorithmic complexity, hot paths, memory pressure, and slow queries. Scoped to performance, not code style (use refactoring/simplify for style)."
triggers: ["optimize performance", "make it faster", "performance", "complexity", "hot path", "memory usage", "slow query", "n+1", "bottleneck"]
depends_on: []
output_schema:
  type: object
  properties:
    findings: {type: array, items: {type: string}}
    optimized: {type: string}
  required: ["findings"]
roles: ["Dev"]
model_tier: "sonnet"
---

# Code Optimizer Skill (performance)

Optimize for **runtime/memory performance only**. For readability/style, defer to the
`refactoring` pack — say so and stop.

1. Identify the dominant cost first — don't micro-optimize cold code. Ask for the hot
   path / input sizes if unknown.
2. Check, in order:
   - **Algorithmic complexity** — O(n^2)→O(n log n)/O(n); nested loops; repeated work
     that can be hoisted/memoized.
   - **Data structures** — wrong container (list scan vs set/dict lookup), needless copies.
   - **I/O & queries** — N+1 queries, missing indexes, unbatched calls, sync-in-loop.
   - **Memory** — needless materialization, generators vs lists, streaming large data.
   - **Concurrency** — parallelizable independent work, blocking calls.
3. Give the **before→after** with the expected complexity/throughput change, and how to
   **measure** it (profile, timeit, EXPLAIN). Never claim a speedup without a mechanism.
4. Preserve behavior — note any correctness/edge-case risk the optimization introduces.
