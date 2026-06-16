# PromptWise — runnable examples

## 1. Recommend a framework (no API key needed)

```bash
PYTHONPATH=src python -c "
from promptwise_v3.core import FrameworkRouter
r = FrameworkRouter()
for task in [
    'Build a HIPAA-compliant patient intake portal from scratch',
    'Refactor the legacy billing module and gate the change',
    'Turn this PRD into a dependency-ordered task list',
    'On every file save, run the linter and update the changelog',
]:
    rec = r.recommend(task)
    print(f'{task[:48]:48s} -> {rec.framework:22s} gate={rec.compliance_gate}')
"
```

Expected: regulated greenfield → Spec Kit (gate=True); brownfield → OpenSpec;
PRD-only → TaskMaster; save-triggered → Kiro-style hooks.

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
