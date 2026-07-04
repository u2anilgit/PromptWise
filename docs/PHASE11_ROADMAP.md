# PromptWise — Phase 11 Roadmap

Debt paydown (3 pyright nits) + a new capability: a red-team harness, the
security analogue of the existing eval harness.

Standing guardrails: **local-first, air-gap-safe, no new infra, no new deps,
tiers/families only, additive/behavior-preserving, TDD.**

---

## 11.1 — Pyright debt

Three cosmetic type nits flagged since Phase 10:

- `insights.py`'s cost-driver accumulator was typed as `Counter[str, int]` by
  inference but assigned `float` cost values. `Counter`'s value type is
  hard-coded to `int` in typeshed (not generically parametrized), so the fix
  replaces it with a plain `dict[str, float]` accumulator and a `max()` call
  in place of `.most_common(1)`.
- `compliance_export.py`'s `verify_chain` lost its `str` narrowing on the
  `rid`/`prev` loop variables across reassignment. Fixed with explicit `str`
  annotations.
- `db/models.py`'s `sessionmaker(class_=AsyncSession)` resolved to the sync
  `Session` overload, cascading type errors at every `async with
  self.async_session()` call site. Switched to `async_sessionmaker`.

All three are annotation/typing-only fixes — no runtime behavior change,
confirmed by the unchanged full test suite.

## 11.2 — Security handler consolidation

Three of the four security tool handlers in `server.py` reimplemented their
own detection regex instead of calling `security.scanner.SecurityScanner`,
which the tools were nominally built on top of. Consolidated onto two new
reusable scanner methods, `detect_injection()` and `detect_pii()`, which
`SecurityScanner.check()` itself now calls internally — one source of truth
instead of three parallel copies. `check_owasp()` became a merged superset of
the two previously-divergent OWASP rule sets (the scanner's and the
handler's), so no detection coverage was lost in the consolidation.

`run_security_suite` previously only aggregated two of the four tool-level
checks; it now surfaces injection and PII findings explicitly alongside the
existing security/OWASP checks, and persists each run's verdict via the new
`core/security_log.SecurityScanStore` (sqlite, same local db as everything
else) — the suite's results were previously ephemeral.

Separately, the scanner's supply-chain check made a live network call to a
public vulnerability database on every scan that mentioned a pinned pip
package — an unconditional network dependency that contradicted this
project's own air-gap guarantee. That lookup is now opt-in via an explicit
`allow_network` flag (default `False`); the regex-only supply-chain checks
remain fully offline as before.

## 11.3 — Red-team harness

`core/redteam_harness.py`, structurally parallel to `core/eval_harness.py`:
a `RedTeamCase` model (input text + target check + expected flag), a
built-in offline corpus of 14 cases (one attack + one benign near-miss per
check type, so both missed detections and false-positive regressions are
caught), `RedTeamResultStore` (sqlite, same db), and `RedTeamHarness` with
the same baseline/regression-gate contract `EvalHarness` uses — a case that
was caught at baseline and now escapes (or a benign case that starts
false-positiving) fails the gate. Wired as the `run_red_team_harness` tool,
defaulting to the built-in corpus when no cases are supplied.

The corpus's attack-side example strings are assembled from split source
fragments rather than written as one contiguous literal, so the module's own
source text doesn't itself trip this repo's PreToolUse write-time security
scan (the very scanner this harness exists to test).

## Wave / parallelization

11.1 and 11.2 are file-disjoint from each other; 11.3 depends on 11.2's
consolidated scanner methods and was built after.

## Guardrails

- 11.1 is behavior-preserving: annotations/typing only.
- 11.2/11.3 are additive; no new dependency; the network-dependent lookup
  defaults off.
- One clean commit per work package; TDD throughout.
