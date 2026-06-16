---
name: design-patterns
description: "Detect a code smell or design problem and recommend the right design pattern (GoF creational/structural/behavioral, concurrency, DDD) with a concrete code example and the tradeoffs."
triggers: ["design pattern", "which pattern", "refactor to pattern", "gof", "anti-pattern", "code smell", "ddd pattern"]
depends_on: []
output_schema:
  type: object
  properties:
    pattern: {type: string}
    rationale: {type: string}
    example: {type: string}
  required: ["pattern", "rationale"]
roles: ["Dev", "Architect"]
model_tier: "sonnet"
---

# Design Patterns Skill

Recommend the fitting design pattern for the described problem or smelly code.

1. Name the **smell / forces** (e.g. rigid construction, conditional sprawl, tight
   coupling, shared mutable state).
2. Recommend ONE primary pattern; name 1–2 alternatives only if genuinely close.
   - Creational: Factory, Builder, Singleton, Prototype.
   - Structural: Adapter, Facade, Decorator, Composite, Proxy.
   - Behavioral: Strategy, Observer, State, Command, Template Method, Chain of Responsibility.
   - Concurrency: Producer-Consumer, Actor, Future/Promise, Read-Write Lock.
   - DDD: Aggregate, Repository, Value Object, Domain Event.
3. Give a short before→after **code example** in the user's language.
4. State the **tradeoff** (what it adds: indirection, classes; what it buys: flexibility).
5. Warn against over-engineering — if a plain function/if-statement is enough, say so.

Do not recommend a pattern where none is warranted; "no pattern needed" is a valid answer.
