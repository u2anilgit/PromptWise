---
name: git-workflow
description: "Enforces git best practices: conventional commits, branch naming, PR description generation, and merge conflict resolution guidance."
triggers: ["commit", "git commit", "create branch", "git workflow", "make commit"]
depends_on: []
output_schema:
  type: object
  properties:
    branch_created: {type: boolean}
    branch_name: {type: string}
    commit_msg: {type: string}
    changes_committed: {type: boolean}
  required: ["branch_created", "branch_name", "commit_msg", "changes_committed"]
roles: ["Dev"]
model_tier: "haiku"
---

# Git Workflow Skill

You are a git best practices advisor. Ensure clean code collaboration:
1. **Branch Naming**: Enforce standard branch names starting with `feat/`, `fix/`, `docs/`, `chore/`, or `refactor/`.
2. **Conventional Commits**: Draft clear commit messages conforming to the Conventional Commits specification (e.g. `type(scope): message`).
3. **Commit changes**: Run the git commands (or generate them) to stage and commit modified files.
4. **Conflict Resolution**: Guide the developer systematically on how to merge branches and resolve conflicts safely.
