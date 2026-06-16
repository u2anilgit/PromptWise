# PromptWise — runnable examples

## 1. Plan a workflow from PromptWise's own skill packs (no API key needed)

```bash
PYTHONPATH=src python -c "
from promptwise_v3.core import WorkflowPlanner
p = WorkflowPlanner()
for task in [
    'Build a HIPAA-compliant patient intake portal from scratch',
    'Refactor the legacy billing module',
    'Write a PRD and user stories for a notifications feature',
]:
    plan = p.plan(task)
    chain = ' -> '.join(s.skill for s in plan.steps)
    print(f'{task[:42]:42s} [{plan.workflow}] gate={plan.compliance_gate}')
    print('   ', chain)
"
```

Expected: regulated greenfield → `greenfield-build+compliance` (gate=True) with
security-architecture + owasp_scan grafted in; brownfield → `brownfield-change`;
docs task → `spec`. Every step is a PromptWise skill pack or built-in tool — runnable
via `invoke_skill`, no external frameworks.

## 2. Route a request to the right model tier

```bash
PYTHONPATH=src python -c "
from promptwise_v3.config import load_config_v3
from promptwise_v3.core import Router
cfg = load_config_v3()
r = Router(cfg).route(text='Extract the dates from this invoice', intent='auto', stakes='auto')
print(r.recommended_model, '-', r.reason)
"
```

## 3. List the skill packs

```bash
PYTHONPATH=src python -c "
from pathlib import Path
from promptwise_v3.core import SkillLoader
sl = SkillLoader(Path('skill_packs'))
sl.load_skills()
print(len(sl.skills), 'skill packs loaded')
"
```
