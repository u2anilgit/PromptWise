---
description: Export a self-verifying, signed compliance evidence bundle from the audit trace via PromptWise.
argument-hint: [optional out_path.zip]
---

Use the PromptWise `export_compliance_bundle` tool to build a tamper-evident evidence
bundle from the hash-chained audit trail. The tool verifies the chain, wraps the records
in a manifest (time range, record count, chain-head digest, generic control-family tags),
and HMAC-signs the bundle with the local key (`PROMPTWISE_AUDIT_KEY` env var or
`PROMPTWISE_AUDIT_KEY_FILE`). If `$ARGUMENTS` names a `.zip` path, pass it as `out_path`
to write the archive.

Then report: record count, whether the hash chain verifies (and the first broken record
if not), whether the signature verifies, the chain-head digest, and where the bundle was
written. Everything runs offline — no network calls.

$ARGUMENTS
