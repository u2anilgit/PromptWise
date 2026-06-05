---
name: changelog-generator
description: Generate Keep-a-Changelog format from git log using conventional commits.
triggers:
  - changelog
  - release notes
  - what changed
  - release changelog
  - keep a changelog
depends_on:
  - git-workflow
output_schema:
  type: object
  properties:
    version:
      type: string
    sections:
      type: object
      description: Grouped changes by Added/Changed/Fixed/Removed
    markdown:
      type: string
      description: Full Keep-a-Changelog formatted Markdown
  required:
    - version
    - markdown
roles:
  - Dev
  - SM
model_tier: haiku
---

# Changelog Generator — Keep-a-Changelog Format

Generate Keep-a-Changelog format from git log. Parse conventional commits: feat→Added, fix→Fixed, refactor→Changed, chore→maintenance (skip), breaking→BREAKING CHANGES. Group by version tag. Format: ## [version] - date, then sections: Added/Changed/Fixed/Removed/Breaking. Output valid Markdown.

## Conventional Commit Mapping

| Commit Type | Changelog Section |
|-------------|-------------------|
| `feat:` | Added |
| `fix:` | Fixed |
| `refactor:` | Changed |
| `perf:` | Changed |
| `docs:` | Changed |
| `style:` | (skip) |
| `chore:` | (skip) |
| `ci:` | (skip) |
| `test:` | (skip) |
| `BREAKING CHANGE:` | Breaking Changes |

## Output Format

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-06-05

### Breaking Changes
- Removed deprecated `foo()` API — use `bar()` instead

### Added
- New feature description ([#123](link))

### Changed
- Refactored X to improve Y

### Fixed
- Bug description ([#456](link))

### Removed
- Deprecated feature removed

[Unreleased]: https://github.com/org/repo/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/org/repo/compare/v1.1.0...v1.2.0
```

## Rules

- Skip commits with no user-facing impact (chore, style, ci, test).
- Strip ticket/issue numbers from commit messages and convert to links if repo URL known.
- Sort entries within each section: most impactful first.
- Scope prefix (e.g., `feat(auth):`) → include scope in parentheses: "**auth**: description".
- `BREAKING CHANGE:` footer or `!` suffix → always goes in Breaking Changes section.

## Process

1. Run `git log --oneline --decorate` to get commit list.
2. Group commits between version tags.
3. Map and filter by type.
4. Format as Markdown.

Return `version` (latest tag or "Unreleased"), `sections` object (keys = section names, values = string arrays), and `markdown` (full changelog string).
