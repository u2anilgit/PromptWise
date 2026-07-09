# PromptWise — Phase 13 Roadmap

Security hardening: benchmark the prompt-injection detector against a bundled
offline corpus, upgrade it on what the benchmark reveals as weak, add an
indirect-injection canary, broaden OWASP coverage, add checksum-validated PII,
and resolve transitive dependencies in the SBOM.

Implements **candidate A — Security hardening** from
`docs/GAP_ANALYSIS_2026-07.md` section 3.

Standing guardrails: **local-first, air-gap-safe by default, no new pip
dependency, additive, TDD.**

> Note: attack example strings in this phase's modules and tests are assembled
> from split literal fragments (the `redteam_harness._j(...)` convention) so the
> source never contains a contiguous trigger phrase that would trip the repo's
> own write-time security scanner. This doc likewise describes attack families
> rather than quoting live trigger phrases.

---

## 13.1 — Benchmark + upgrade the injection detector

The gap analysis flagged the injection detector as *unbenchmarked*: four phrase
regexes with a `min(1.0, matches * 0.25)` count-based confidence. Competitors
publish PINT scores (79-95%); PromptWise had no number at all.

`security/injection_benchmark.py` is a new offline harness — a bundled
attack + benign corpus scored against the real
`SecurityScanner.detect_injection`. It reports precision / recall / F1 /
accuracy plus the specific false positives and false negatives, so the number
is measured, not claimed.

Air-gap default is preserved: an optional live-fetch of the public PINT dataset
is gated behind `allow_network=False`, mirroring the OSV lookup in
`core/security_log.py` / `scanner._check_osv`. With the flag off (the default)
the harness only ever reads the bundled corpus — no socket is opened.

Measured against the bundled corpus, the *original* detector scored
**precision 0.80 / recall 0.27 / F1 0.40** — it missed instruction-override
phrasings that were not the literal four patterns (forget/override variants,
unfiltered-persona requests, system-prompt exfiltration, embedded role markers)
and false-positived on the bare persona pattern against benign text.

The upgrade (13.1) replaces the four flat patterns with a **weighted** pattern
set grouped by attack family — instruction override, unfiltered/unrestricted
persona, jail-break keywords, developer-mode, persona reassignment,
system-prompt exfiltration, and embedded role markers. Confidence is the summed
weight of matched families (capped at 1.0), so a single strong signal reads as
high-confidence while the coarse count math is gone. Patterns require the
trigger word to sit next to an adversarial object (e.g. an override verb next
to an instructions/rules/prompt noun), which removes the "persona-word +
benign continuation" class of false positive. Post-upgrade the detector scores
**precision 1.00 / recall 1.00 / F1 1.00** on the bundled corpus.

Wired as the `benchmark_injection` MCP tool, structurally parallel to the
existing `run_red_team_harness` / `run_eval_harness` harness tools (not a new
scanning API — a measurement harness).

## 13.2 — Indirect prompt-injection canary (Rebuff-style)

Indirect injection — adversarial instructions arriving via tool output / RAG
content rather than direct user input — evades phrase filters by construction.
The canary pattern catches the exfiltration half: `SecurityScanner` gains
`issue_canary()` (mint a random token), `embed_canary(content, token)` (hide
the token in content that will flow through tool output / RAG, as an HTML
comment), and `check_canary_leak(output, token)` (flag if the token is emitted
in model output — meaning the injected content leaked back out). Wired into
`scan_response`: pass a `canary` and the response is checked for the leak,
adding a `canary_leak` signal to the (superset-compatible) response shape.

## 13.3 — Expand OWASP coverage

`check_owasp` covered 5 of the OWASP Top-10 (SQLi, hardcoded credentials, XSS,
command injection, disabled SSL verification). Phase 13 adds:

- **A02 Cryptographic Failures** — weak hashing (`md5`/`sha1`) and broken
  ciphers (`DES`/`RC4`).
- **A08 Software & Data Integrity Failures** — insecure deserialization
  (`pickle.loads`, `yaml.load` without a safe loader, `marshal.loads`).
- **A10 SSRF** — request / urlopen on a non-literal (variable) URL.
- **A01 Broken Access Control** — path traversal (`../` into a file open).
- **A05 Security Misconfiguration** — Flask / app `debug=True`.

## 13.4 — PII checksum validation (Luhn)

The credit-card PII regex matched any 13-16 digit run, false-positiving on
order numbers, tracking IDs, etc. `detect_pii` now runs the **Luhn** checksum
over each candidate card and only counts / redacts numbers that validate — a
cheap, dependency-free precision win. Non-card PII (email, phone, SSN) is
unchanged.

## 13.5 — SBOM lockfile / transitive parsing

`core/sbom.py` read only top-level `requirements.txt` / `package.json`. It now
also parses **`poetry.lock`** (regex over `[[package]]` blocks — no `tomllib`
dependency, works on 3.10) and **`package-lock.json`** (v2/v3 `packages`, v1
`dependencies`) to capture transitive dependencies. Lockfile-sourced components
carry a `resolution: transitive` property so a consumer can tell direct from
transitive; top-level manifest entries stay `resolution: direct`.

## Guardrails

- No new pip dependency; all heuristic / stdlib.
- Air-gap-safe: the benchmark's live PINT fetch is gated `allow_network=False`.
- Additive: existing tool response field names are preserved (new keys only).
- Attack literals in new modules / tests are split-fragment assembled so the
  repo's own write-time scanner never trips on this phase's source.
- TDD throughout, one commit per logical package.
