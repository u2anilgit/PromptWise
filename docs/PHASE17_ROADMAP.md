# PromptWise — Phase 17 Roadmap

Candidate **G — Multi-platform emitters**, from `docs/GAP_ANALYSIS_2026-07.md` §7.
Closes the gap between the README's "multi-platform" framing and actual host
coverage, and scopes a structurally new distribution mode (web-chat bundle)
without bending the existing IDE-emitter abstraction to fit it.

Standing guardrails: **local-first, air-gap-safe, no new infra, no new pip
dependencies, no branded/competitor model ids, additive where possible, TDD,
one clean commit per package.**

---

## 17.1 — Windsurf emitter

**Gap:** `core/config_emitter.TARGETS` covers 6 hosts (claude, agents/codex,
cursor, copilot, cline, gemini) but not Windsurf. Windsurf/Cascade's rules
convention is a single plain file at the repo root — the same shape as the
existing `cline` emitter (`.clinerules`), not the frontmatter-bearing `.mdc`
shape Cursor needs. `.windsurfrules` remains the widely-supported convention
(newer Windsurf/Cascade builds also read a `.windsurf/rules/` directory, but
the single-file form is still recognized and is the simplest, most stable
target — same reasoning that kept the Cline emitter to one flat file).

**Plan:**
- `TARGETS["windsurf"] = ".windsurfrules"`.
- `ConfigEmitter.emit_windsurf(bundle) -> str`: same flat-body render as
  `emit_cline`/`emit_gemini` — no frontmatter, no profile lookup.
- No new `AgentProfile` entry (mirrors `cline`, which also has none —
  `_EMITTER_TO_PROFILE` stays untouched, so `_lint_warnings` cleanly returns
  `[]` for this target exactly as it already does for `cline`).
- Managed-block merge, `sync`/`diff`/`check` modes, and `check_portability`
  all pick this target up for free — they iterate `TARGETS` generically.

## 17.2 — JetBrains AI Assistant emitter

**Gap:** same as above for JetBrains AI Assistant / Junie. Current convention
is `.aiassistant/rules/<name>.md` — Markdown body; the *type* of a rule
(always / manually / by-file-pattern / by-model-decision) is configured
through IDE settings rather than in-file frontmatter, so (unlike Cursor) no
frontmatter is required in the emitted file.

**Plan:**
- `TARGETS["jetbrains"] = ".aiassistant/rules/promptwise.md"`.
- `ConfigEmitter.emit_jetbrains(bundle) -> str`: flat body render, same shape
  as `emit_windsurf`.
- No new `AgentProfile` entry, same reasoning as 17.1.
- Golden file `tests/goldens/jetbrains.golden` added alongside the others.

## 17.3 — Web-agent single-file bundle

BMAD-derived idea (gap-analysis §7): a governed agent usable directly by
pasting into ChatGPT / Gemini / Claude.ai web chat — no IDE, no CLI, no MCP
host, so there is no native config file to merge into and nothing to wire a
tool-calling surface to. This is **not** an IDE emitter wearing a different
hat: it doesn't go in `TARGETS`, doesn't use `merge_managed` (there is no
user-owned region to preserve — the whole file *is* the bundle, and
regenerating always fully replaces it), and isn't reachable through
`sync_agent_config`.

**Plan:**
- New module `core/web_bundle.py`, `WebBundleEmitter`:
  - `.render(bundle, skill_root="skill_packs", include_packs=True) -> str` —
    flattens the `GovernanceBundle` (method, policy, house rules) plus the
    body of each active pack in `bundle.packs` into one pasteable Markdown
    document, framed with instructions for a human pasting it into a web
    chat's first message / system-prompt box.
  - Pack lookup reuses `promptwise.core.skill_loader.SkillLoader` (name →
    `Skill.system_prompt`) instead of re-parsing `SKILL.md` frontmatter —
    composition over reinvention, same convention Phase 12's `rank_context`
    established. A pack that can't be found is a placeholder line, never a
    hard failure (fail-soft, matches the rest of the emitter surface).
  - `.write(bundle, out_path, ...)` renders and writes one standalone file
    (parent dirs created as needed); no managed-block bookkeeping.
- New MCP tool `export_web_bundle`, registered the normal way (`_TOOL_DEFS` +
  `_HANDLERS`, covered by the existing bijection test in
  `tests/test_tool_registry.py`) — this satisfies "wire through the existing
  MCP tool surface" without forcing the web bundle into
  `sync_agent_config`'s host list, which is reserved for the merge-managed
  IDE/CLI emitters.

## Guardrails recap

- No new dependency, no network, no new persistence beyond an explicit
  single-file write the caller opts into.
- Existing 6 emitters, their goldens, and `check_portability` are untouched
  except for the additive `TARGETS` entries picked up generically.
- TDD throughout; one commit per package (17.1, 17.2, 17.3).
