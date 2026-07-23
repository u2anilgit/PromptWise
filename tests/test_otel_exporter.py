"""Task 6 (P1) — OpenTelemetry GenAI semantic-convention exporter.

Hand-rolled OTLP-JSON translation layer over existing cost_report/export_audit
data -- no new third-party dependency (stdlib-only project convention), so no
opentelemetry-sdk. Only genuine ``gen_ai.*`` attribute names from the
OpenTelemetry GenAI semantic conventions registry (verified 2026-07-23,
https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/) are
used; anything the registry doesn't define (skill name, USD cost) is emitted
under a ``promptwise.*`` extension namespace, never disguised as an official
gen_ai.* attribute.
"""
import asyncio
import json
import typing

from promptwise.core.otel_exporter import cost_report_to_otlp_metrics, audit_records_to_otlp_spans
from promptwise import server as srv
from promptwise.core import tool_registry as _tool_registry_mod


def test_cost_report_emits_one_data_point_per_skill_with_gen_ai_and_promptwise_attrs():
    report = {"period": "weekly", "project_id": "proj-1",
              "total_cost_usd": 1.5,
              "by_skill": {"deslop": {"cost_usd": 1.0, "calls": 3},
                           "route": {"cost_usd": 0.5, "calls": 1}}}
    otlp = cost_report_to_otlp_metrics(report)
    metric = otlp["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]
    assert metric["name"] == "promptwise.cost.usd"
    points = metric["gauge"]["dataPoints"]
    assert len(points) == 2
    by_skill = {}
    for p in points:
        attrs = {a["key"]: a["value"] for a in p["attributes"]}
        by_skill[attrs["promptwise.skill"]["stringValue"]] = p
    assert by_skill["deslop"]["asDouble"] == 1.0
    deslop_attrs = {a["key"]: a["value"] for a in by_skill["deslop"]["attributes"]}
    assert deslop_attrs["promptwise.calls"]["intValue"] == "3" or deslop_attrs["promptwise.calls"]["intValue"] == 3


def test_cost_report_is_valid_json_serializable():
    report = {"period": "weekly", "project_id": None, "total_cost_usd": 0.0, "by_skill": {}}
    otlp = cost_report_to_otlp_metrics(report)
    json.dumps(otlp)  # must not raise
    assert otlp["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]["gauge"]["dataPoints"] == []


def test_audit_records_become_otlp_spans_with_gen_ai_request_model():
    records = [
        {"index": 0, "timestamp": "2026-07-23T00:00:00+00:00", "task": "rewrite_prompt",
         "actor": "claude-code", "agent": "claude-code", "model": "claude-sonnet-4-6",
         "cost_usd": 0.002, "hash": "abc123"},
    ]
    otlp = audit_records_to_otlp_spans(records)
    span = otlp["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    attrs = {a["key"]: a["value"] for a in span["attributes"]}
    assert span["name"] == "rewrite_prompt"
    assert attrs["gen_ai.request.model"]["stringValue"] == "claude-sonnet-4-6"
    assert attrs["gen_ai.operation.name"]["stringValue"] == "rewrite_prompt"
    assert attrs["promptwise.cost.usd"]["doubleValue"] == 0.002


def test_audit_records_to_otlp_spans_handles_empty_list():
    otlp = audit_records_to_otlp_spans([])
    assert otlp["resourceSpans"][0]["scopeSpans"][0]["spans"] == []
    json.dumps(otlp)


def _call(name, arguments, ctx=None):
    coro = typing.cast(
        "typing.Coroutine[typing.Any, typing.Any, str]",
        srv._HANDLERS[name](typing.cast(srv.ServerContext, ctx), arguments),
    )
    return asyncio.run(coro)


def test_export_audit_handler_otlp_format_emits_otlp_spans(tmp_path, monkeypatch):
    from promptwise.core.audit_log import AuditLog
    fresh = AuditLog(tmp_path / "audit.jsonl")
    fresh.append(task="rewrite_prompt", actor="claude-code", agent="claude-code",
                 model="claude-sonnet-4-6", cost_usd=0.001)
    # _get_audit_log's real module-level cache lives in core/tool_registry.py
    # (server.py only re-exports the function itself for back-compat), so the
    # monkeypatch has to target the module that actually owns the global.
    monkeypatch.setattr(_tool_registry_mod, "_AUDIT_LOG", fresh)

    out = json.loads(_call("export_audit", {"format": "otlp"}))
    assert "otlp" in out
    assert "json" not in out and "text" not in out
    span = out["otlp"]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["name"] == "rewrite_prompt"
