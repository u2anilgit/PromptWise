# Security Policy

PromptWise is a governance and intelligence layer for AI coding agents. Security is
the product, so we hold the codebase to the same bar it enforces for others.

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.2.x   | ✅ |
| 1.1.x   | ✅ |
| < 1.1   | ❌ |

## Reporting a vulnerability

Please report security issues privately — **do not open a public issue** for an
exploitable vulnerability.

- Email: **u2anil@gmail.com** with subject `PromptWise security`.
- Include: affected version, a description, reproduction steps, and impact.
- We aim to acknowledge within 5 business days and to ship a fix or mitigation for
  confirmed high-severity issues as a priority.

Please give us a reasonable window to remediate before any public disclosure.

## Security posture

- **Local-first / air-gapped safe.** Core functionality runs with no network and no
  API key. The only outbound call is an optional OSV vulnerability lookup in
  `security/scanner.py` (1.5s timeout, fails open) when a pinned `pip install` is
  scanned; everything else is offline. Persistence is local SQLite / JSONL under
  `~/.promptwise/` and project-local `.promptwise/`.
- **Fail-open enforcement.** The Claude Code lifecycle hooks in `hooks/` enforce
  security, policy, and audit at runtime and can block (e.g. secret writes, runaway
  tool loops). Any hook error fails open — it never wedges the session — and is logged.
- **Tamper-evident trace.** Audited changes are recorded in a SHA-256 hash-chained log
  (`core/audit_log.py`) that can be re-verified end to end.
- **Supply-chain awareness.** `audit_mcp_servers` inspects declared MCP servers for
  pipe-to-shell installs, plaintext endpoints, inline secrets, and broad allow-surface.

## Scope notes

- The bundled scanners (secrets, OWASP, injection, PII) are heuristic aids, not a
  substitute for a dedicated SAST/secret-scanning pipeline. Treat findings as signal.
- Hooks execute local Python the user has installed as a Claude Code plugin; review
  `hooks/` before enabling, as you would any plugin that can block tool calls.
