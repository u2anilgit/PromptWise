---
name: multi-model-eval
description: Evaluate a prompt across Claude model tiers and recommend the best cost-quality trade-off.
triggers:
  - compare models
  - evaluate models
  - model evaluation
  - which model
  - benchmark prompt
  - model comparison
depends_on: []
output_schema:
  type: object
  properties:
    prompt:
      type: string
    evaluations:
      type: object
    winner:
      type: string
    recommendation:
      type: string
  required:
    - evaluations
    - winner
roles:
  - Dev
  - IT
model_tier: opus
---

# Multi-Model Eval

Evaluate a prompt across multiple Claude model tiers and recommend the best option.

## Process

### Step 1 — Run the prompt on each tier
Execute the prompt against:
- `haiku` — fastest, cheapest
- `sonnet` — balanced
- `opus` — highest quality

Capture each model's response text, estimated latency (ms), and cost per call (USD).

### Step 2 — Opus judges each response
Using Opus as the authoritative judge, score every response (0–100) on four dimensions:
| Dimension | Weight |
|-----------|--------|
| Accuracy | 35% |
| Completeness | 25% |
| Reasoning | 25% |
| Safety / Tone | 15% |

Compute `quality_score` as the weighted average.

### Step 3 — Compute cost-adjusted quality
```
cost_adjusted = quality_score / cost_usd
```
Higher is better. This rewards cheaper models that deliver similar quality.

### Step 4 — Rank and select winner
Rank all three tiers by `cost_adjusted`. The winner is the tier with the highest score.

## Output shape

```json
{
  "prompt": "<the evaluated prompt>",
  "evaluations": {
    "haiku":  { "quality_score": 72, "latency_ms": 320, "cost_usd": 0.0004, "cost_adjusted": 180000 },
    "sonnet": { "quality_score": 88, "latency_ms": 950, "cost_usd": 0.003,  "cost_adjusted": 29333 },
    "opus":   { "quality_score": 96, "latency_ms": 2400, "cost_usd": 0.015, "cost_adjusted": 6400 }
  },
  "winner": "haiku",
  "recommendation": "Haiku delivers 75% of Opus quality at 3% of the cost for this summarization task. Use Opus only if accuracy > 90 is a hard requirement."
}
```

## Notes

- If a task requires complex multi-step reasoning, bias toward Sonnet/Opus even when cost_adjusted favors Haiku.
- Always include a qualitative rationale in `recommendation`.
- Surface any safety or refusal differences between tiers.
