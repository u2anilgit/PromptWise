---
name: model-migration-advisor
description: Guide migration between Claude model versions — identify affected prompts, surface breaking changes, estimate cost delta, and produce an ordered migration plan.
triggers:
  - migrate model
  - model upgrade
  - switch model
  - model deprecation
  - update claude version
depends_on:
  - multi-model-eval
output_schema:
  type: object
  properties:
    source_model:
      type: string
    target_model:
      type: string
    migration_checklist:
      type: array
      items:
        type: string
    breaking_changes:
      type: array
      items:
        type: string
    estimated_cost_delta:
      type: string
  required:
    - migration_checklist
    - breaking_changes
roles:
  - Dev
  - IT
model_tier: sonnet
---

# Model Migration Advisor

Guide a safe, well-tested migration from one Claude model version to another.

## Step 1 — Identify affected prompts

Scan the codebase and prompt registry for all references to the `source_model`:
- Hardcoded model IDs in code (e.g. `claude-3-haiku-20240307`)
- Config files referencing the model tier
- Skill files with `model_tier` matching source

List every call site with file path and line number.

## Step 2 — Evaluate source vs. target

Invoke `multi-model-eval` on a representative sample of the affected prompts (up to 5). Compare:
- Quality score delta (target − source)
- Cost per call delta
- Latency delta

Surface any cases where target quality is meaningfully lower (Δ < −10 points).

## Step 3 — Check for breaking changes

Known breaking change categories to check:
- **Parameter names**: have any API parameters been renamed or removed? (e.g. `max_tokens_to_sample` → `max_tokens`)
- **Context window limits**: does the target model have a different max context length?
- **Tool/function calling format**: any schema differences in tool definitions?
- **Output format changes**: does the target produce different JSON structure or streaming format?
- **Behavior differences**: does the target refuse or handle certain inputs differently?
- **Deprecated features**: computer use API, legacy vision endpoints, etc.

For each breaking change found, provide: `"<change description> — Action required: <what to do>"`.

## Step 4 — Generate migration checklist

Produce an ordered checklist of tasks to complete the migration safely:

1. [ ] Run `multi-model-eval` on all affected prompts
2. [ ] Update model ID in config files
3. [ ] Update hardcoded model IDs in code
4. [ ] Adjust parameter names for any breaking API changes
5. [ ] Update context window limits in chunking/RAG config if needed
6. [ ] Re-run test suite against target model
7. [ ] Validate outputs with `validate_output` on all affected skills
8. [ ] Deploy to staging and run smoke tests
9. [ ] Monitor error rates for 24 h post-deployment
10. [ ] Update prompt registry entries with new `model_tier`

Customize the list based on findings from steps 1–3.

## Step 5 — Estimate cost delta

Calculate:
```
delta_per_call = target_cost_usd - source_cost_usd
monthly_volume = (estimated or provided call volume)
monthly_delta_usd = delta_per_call * monthly_volume
```

Express as: `"+$X.XX/month (+Y%)"` or `"-$X.XX/month (-Y%)"`.

If volume is unknown, state the per-call delta only.

## Output

Return `source_model`, `target_model`, `migration_checklist` (ordered string array), `breaking_changes` (string array, empty if none), and `estimated_cost_delta` (string).
