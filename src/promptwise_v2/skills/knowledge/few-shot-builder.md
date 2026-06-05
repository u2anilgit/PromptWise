---
name: few-shot-builder
description: Build diverse, ordered few-shot example sets for prompts, pulling from the prompt registry and generating synthetic coverage.
triggers:
  - few shot
  - examples
  - build examples
  - in-context learning
  - prompt examples
  - training examples
depends_on:
  - prompt-registry
output_schema:
  type: object
  properties:
    examples:
      type: array
      items:
        type: object
    example_count:
      type: integer
    coverage_gaps:
      type: array
      items:
        type: string
  required:
    - examples
    - example_count
roles:
  - Dev
model_tier: sonnet
---

# Few-Shot Builder

Construct high-quality few-shot example sets for prompts.

## Step 1 — Identify task type

Classify the prompt into one of:
- `classification` — assign a label from a fixed set
- `generation` — produce open-ended text
- `extraction` — pull structured data from unstructured input
- `qa` — answer questions from context

The task type determines what "diverse" means for coverage.

## Step 2 — Pull examples from prompt registry

Query the prompt registry (`prompt-registry` skill) for existing examples tagged to this prompt or task type. Prefer examples that:
- Cover different input lengths (short / medium / long)
- Represent varied domains or styles
- Include at least one edge case (empty input, ambiguous phrasing, boundary values)

## Step 3 — Identify and fill coverage gaps

Detect under-represented scenarios:
- For classification: are all label classes represented?
- For extraction: are nested/missing fields covered?
- For generation: are different tones/formats covered?
- For QA: are unanswerable questions included?

Generate synthetic examples to fill gaps. Each synthetic example must be clearly plausible, not contrived.

## Step 4 — Order examples

Sort from **simple → complex**:
1. Clear, canonical case
2. Common variation
3. Edge case or adversarial input

## Output rules

- Return 3–10 examples total (prefer fewer, higher-quality examples).
- Each example object: `{input, expected_output, explanation}`.
- `explanation` is one sentence — why this example is in the set.
- List `coverage_gaps` even if all gaps were filled (shows what was synthesized).

## Example output shape

```json
{
  "examples": [
    {
      "input": "Summarize: The meeting was productive.",
      "expected_output": "Productive meeting.",
      "explanation": "Canonical short-input case."
    }
  ],
  "example_count": 5,
  "coverage_gaps": ["multi-paragraph input", "non-English input"]
}
```
