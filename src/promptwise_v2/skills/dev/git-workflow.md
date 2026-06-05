---
name: git-workflow
description: Generate Conventional Commits messages, branch names, and PR descriptions following project standards.
triggers:
  - commit
  - git
  - branch
  - pr description
  - pull request
  - conventional commit
depends_on: []
output_schema:
  type: object
  properties:
    commit_message:
      type: string
      description: Conventional Commits formatted commit message
    branch_name:
      type: string
      description: Kebab-case branch name following type/short-description pattern
    pr_description:
      type: string
      description: Pull request description with Summary bullets and Test plan checklist
  required:
    - commit_message
    - branch_name
    - pr_description
roles:
  - Dev
model_tier: haiku
---

# Git Workflow

Conventional Commits format: type(scope): subject. Types: feat/fix/docs/chore/refactor/test. Subject ≤50 chars, imperative mood. Body only when WHY isn't obvious. Branch: type/short-description. PR: Summary (bullets) + Test plan (checklist).

## Commit Message Format

```
type(scope): subject

[optional body — only when WHY is not obvious from the subject]

[optional footer: BREAKING CHANGE, Co-Authored-By, etc.]
```

### Types
- `feat`: new feature or capability
- `fix`: bug fix
- `docs`: documentation only
- `chore`: build, tooling, dependencies — no production code change
- `refactor`: code restructuring with no behavior change
- `test`: adding or modifying tests only
- `perf`: performance improvement

### Subject Rules
- ≤50 characters
- Imperative mood: "add user login" not "added user login" or "adds user login"
- No period at the end
- Lowercase after the colon

### Body Rules
- Add a body only when the subject line cannot capture WHY the change was made
- Wrap at 72 characters
- Separate from subject with a blank line

## Branch Naming

Pattern: `type/short-description`

Examples:
- `feat/user-auth`
- `fix/login-redirect`
- `refactor/payment-module`
- `chore/update-deps`

Rules: lowercase, hyphens only, no spaces, ≤40 characters total.

## PR Description Format

```markdown
## Summary
- Bullet point 1: what changed
- Bullet point 2: why it changed
- Bullet point 3: any notable design decisions

## Test plan
- [ ] Unit tests pass
- [ ] Manual test: [specific scenario]
- [ ] Edge case: [specific edge case tested]
```

## Output

Return the commit message, branch name, and full PR description.
