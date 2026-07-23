"""otel_exporter — OpenTelemetry GenAI semantic-convention exporter (P1 Task 6).

Hand-rolled OTLP-JSON translation layer over existing ``cost_report`` /
``export_audit`` data. No new dependency: this project is stdlib-only,
offline-first, air-gap-safe (same convention as ``mcp_auditor.py`` /
``portability_check.py``), so this module builds the OTLP JSON payload shape
by hand rather than depending on the ``opentelemetry-sdk`` package. That is a
real trade-off, not a shortcut: it means we do not get the upstream SDK's
batching/retry/exporter machinery, only the wire-shape translation. A team
that wants live OTLP export over gRPC/HTTP can feed this module's output to
any OTLP-JSON-compatible collector endpoint themselves.

Attribute provenance: every ``gen_ai.*`` attribute key below is copied from
the OpenTelemetry GenAI semantic conventions attribute registry, verified
2026-07-23 at https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/
(``gen_ai.request.model``, ``gen_ai.operation.name``). Concepts that
registry does not define -- USD cost, PromptWise's internal "skill" name,
call counts -- are emitted under a ``promptwise.*`` extension namespace,
never disguised as an official ``gen_ai.*`` key. This follows the same
anti-fabrication discipline as ``framework_map.py`` (P1 Task 4).
"""
from __future__ import annotations

_SCOPE_NAME = "promptwise"


def _attr(key: str, value) -> dict:
    """One OTLP-JSON ``KeyValue`` (``{"key": ..., "value": {...}}``)."""
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": value}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": "" if value is None else str(value)}}


def cost_report_to_otlp_metrics(report: dict, service_name: str = "promptwise") -> dict:
    """Translate a ``cost_report`` tool result into an OTLP JSON
    ``resourceMetrics`` payload: one gauge data point per skill, carrying its
    USD cost (``promptwise.cost.usd``, the metric itself) plus extension
    attributes for the skill name and call count. No token counts appear
    here because ``cost_report`` doesn't track them -- see
    ``audit_records_to_otlp_spans`` for the record-level gen_ai.* attributes.
    """
    by_skill = report.get("by_skill") or {}
    points = []
    for skill, data in by_skill.items():
        points.append({
            "asDouble": float(data.get("cost_usd", 0.0)),
            "attributes": [
                _attr("promptwise.skill", skill),
                _attr("promptwise.calls", int(data.get("calls", 0))),
                _attr("promptwise.period", report.get("period", "")),
            ],
        })
    return {
        "resourceMetrics": [{
            "resource": {"attributes": [_attr("service.name", service_name)]},
            "scopeMetrics": [{
                "scope": {"name": _SCOPE_NAME},
                "metrics": [{
                    "name": "promptwise.cost.usd",
                    "description": "USD cost attributed to a PromptWise skill invocation (extension metric; not part of the gen_ai.* semconv registry).",
                    "unit": "USD",
                    "gauge": {"dataPoints": points},
                }],
            }],
        }],
    }


def audit_records_to_otlp_spans(records: list[dict], service_name: str = "promptwise") -> dict:
    """Translate audit-trail records (``export_audit``'s ``json`` field) into
    an OTLP JSON ``resourceSpans`` payload: one span per record, using the
    verified ``gen_ai.request.model`` / ``gen_ai.operation.name`` attributes
    for the model and task, plus a ``promptwise.cost.usd`` extension
    attribute and the audit hash-chain fields for traceability.
    """
    spans = []
    for r in records:
        attrs = [
            _attr("gen_ai.operation.name", r.get("task", "")),
            _attr("gen_ai.request.model", r.get("model", "")),
            _attr("promptwise.cost.usd", float(r.get("cost_usd", 0.0))),
            _attr("promptwise.actor", r.get("actor", "")),
            _attr("promptwise.agent", r.get("agent", "")),
            _attr("promptwise.audit.hash", r.get("hash", "")),
        ]
        spans.append({
            "name": r.get("task", ""),
            "startTimeUnixNano": _iso_to_unix_nano(r.get("timestamp", "")),
            "attributes": attrs,
        })
    return {
        "resourceSpans": [{
            "resource": {"attributes": [_attr("service.name", service_name)]},
            "scopeSpans": [{
                "scope": {"name": _SCOPE_NAME},
                "spans": spans,
            }],
        }],
    }


def _iso_to_unix_nano(timestamp: str) -> int:
    """Best-effort ISO-8601 -> unix nanoseconds for OTLP JSON's expected
    string-encoded uint64. Malformed/missing timestamps yield 0 rather than
    raising -- a span with an unparsed time is still useful; a crashed
    export is not."""
    if not timestamp:
        return 0
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp)
        return int(dt.timestamp() * 1_000_000_000)
    except Exception:
        return 0
