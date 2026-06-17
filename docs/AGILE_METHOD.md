# PromptWise Agile Method + Governance

A native, self-contained agile-AI-development method (BMAD-style) plus a cross-agent
governance plane. **Additive** to PromptWise core — no third-party framework, no network,
license-clean (see `NOTICE`).

## The shape

Two phases, mapped onto model-tier routing for a cost win:

```
planning  (opus tier):     analyst → pm → [ux] → architect → po(shard+validate)
dev loop  (sonnet tier):   per story →  sm(draft) → dev(implement) → qa(quality-gate)
```

Regulated tasks graft security in automatically: `security-architecture` into planning,
`owasp_scan` + `get_sbom` into the dev loop, and the compliance rules ride **into** each
story's `dev_notes`.

## Personas (skill packs)

Nine packs under `skill_packs/agile/`, auto-discovered by `SkillLoader`. Each orchestrates
an existing PromptWise pack via `depends_on` — the persona frames, the dependency does the work.

| Pack | Role | Depends on |
|---|---|---|
| `agile-analyst` | discovery, project brief | `brd-generator` |
| `agile-pm` | PRD → epics/stories | `prd-generator` |
| `agile-architect` | architecture + NFR | `system-design` |
| `agile-po` | cohesion check + shard | `verification-before-completion` |
| `agile-sm` | draft context-rich story | `user-story-generator` |
| `agile-dev` | implement one story | `tdd`, `feature-dev` |
| `agile-qa` | risk + quality gate | `test-generator`, `code-review`, `threat-modeler` |
| `agile-ux` | optional UI spec | `system-design` |
| `agile-orchestrator` | route + handoffs | `plan_workflow`, `suggest_skill` |

Invoke any persona via the existing `invoke_skill` tool, or list them with `list_skills`
(they appear as `agile-*`).

## MCP tools

| Tool | Does | Composes |
|---|---|---|
| `agile_plan` | two-phase persona plan + tiers + compliance flag | `agile_planner` |
| `shard_doc` | split PRD/architecture md into anchored shards | `doc_sharder` |
| `draft_story` | self-contained, context-engineered story | `story_context` |
| `run_quality_gate` | advisory PASS/CONCERNS/FAIL/WAIVED decision | `quality_gate` |
| `check_policy` | evaluate action vs governance policy | `policy` |
| `record_audit` | append hash-chained AI-change record | `audit_log` |
| `export_audit` | export the audit trail (JSON + text) + verify chain | `audit_log` |
| `sync_agent_config` | one governance source → every agent's rules file | `config_emitter` |

The read-only/safe tools are in `.mcp.json` `alwaysAllow`. `record_audit` and
`sync_agent_config` write files, so they prompt by default.

## The signature artifacts

**Context-engineered story** (`draft_story`) — a story whose `dev_notes` embed the relevant
architecture shards, files to touch, constraints, and compliance rules inline. The dev
executor needs no external lookup. This *is* an audit artifact: it carries *why* each
decision was made and which compliance rules apply.

**Quality gate** (`run_quality_gate`) — deterministic, auditable decision:
- unresolved high/critical finding → `FAIL` (or `WAIVED` if a waiver reason is supplied, recorded for audit)
- medium finding or `risk_score ≥ threshold` → `CONCERNS`
- else → `PASS`

**Audit trail** (`record_audit` / `export_audit`) — append-only, SHA-256 hash-chained record
of every governed task (task → agent → model → cost → rules → gate decision → files). Any
edit breaks the chain; `export_audit` reports `chain_ok`.

**Policy-as-code** (`check_policy`) — one `config/policy.yaml` (budget cap, allowed model
tiers, banned operations, required gates) enforced identically regardless of agent.

## Configuration

- `config/agile.yaml` — persona order, model-tier map, gate thresholds, regulated graft.
- `config/policy.yaml` — governance policy. Copy from `config/policy.example.yaml` and tune
  (`check_policy` needs this file present).

## The cross-agent demo

```text
sync_agent_config(
  project="acme",
  policy_summary=["Budget $5/day", "Tiers: haiku/sonnet"],
  packs=["banking", "agile-sm", "agile-qa"],
  targets=["claude", "cursor", "copilot"])
# writes CLAUDE.md, .cursor/rules/promptwise.mdc, .github/copilot-instructions.md
# — identical policy + method in every agent.
```

## Tests

```bash
python -m pytest tests/test_agile_governance.py -q   # 9 — core modules
python -m pytest tests/test_agile_planner.py -q      # 5 — two-phase planner
python -m pytest tests -q                            # full suite (40), zero regressions
```
