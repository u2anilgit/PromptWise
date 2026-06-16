# Configuring PromptWise

All config is YAML in `config/`, loaded from the repo root at startup. Hot-reload at
runtime with the `reload_config` tool. A fuller field reference lives in
`docs/integration/CONFIGURATION_REFERENCE.md`.

## Files

| File | Purpose |
|------|---------|
| `config/promptwise_v3.yaml` | Main config: models, providers, roles, security, policies, skills dir, timeouts |
| `config/role_keywords.yaml` | Keyword → role mapping for `detect_role` |
| `config/model_strategy.yaml` | Routing strategy hints |
| `config/compliance/*.yaml` | Per-domain compliance rule sets (banking, healthcare, legal) |
| `pricing.yaml` · `providers.yaml` · `roles.yaml` | Standalone pricing / provider / role tables |

## Key sections in `promptwise_v3.yaml`

```yaml
default_model: claude-sonnet-4-6

policies:
  budget_hard_stop_usd: 10.0      # hard spend ceiling
  daily_burn_warn_usd: 3.0
  team_budget_usd: 100.0
  max_tokens_per_session: 500000

security:
  pii_detection: true
  pii_action: redact              # redact | warn | block
  injection_detection: true
  injection_threshold: 0.7        # 0–1; higher = stricter

skills:
  directory: skill_packs/         # where the 63 packs live (loaded by SkillLoader)
  auto_trigger: true
  confidence_threshold: 0.6

timeout:
  idle_threshold_minutes: 30
  warn_threshold_minutes: 20
```

## Common changes

- **Set a budget cap** → `policies.budget_hard_stop_usd`, then `set_budget_limit` at runtime.
- **Tighten injection scanning** → raise `security.injection_threshold`.
- **Add your own skill packs** → drop a `SKILL.md` into `skill_packs/<category>/`; it loads
  on next start (or `reload_config`). Frontmatter needs `name`, `description`, `triggers`.
- **Change pricing** → edit `pricing.yaml` / the `models:` block, then `reload_config`.

## Environment

- `PYTHONPATH=src` (or `pip install -e .`) so `promptwise_v3` is importable.
- No API keys are required for routing, scanning, diagrams, tracking, or workflow planning
  — those run locally. Keys are only needed if you wire live model calls yourself.

## Resetting

Runtime state is in `~/.promptwise/promptwise_v3.db`. Remove it to clear sessions, costs,
tasks, and ROI history. Config files are never modified at runtime.
