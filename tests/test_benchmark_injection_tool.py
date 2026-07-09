"""Phase 13.1 — benchmark_injection MCP tool wiring.

The tool runs the offline injection benchmark against the real scanner and
returns the measured metrics (a number, not a claim). Offline by default.
"""
import asyncio
import json

from promptwise.security.scanner import SecurityScanner
from promptwise import server as srv


class _Ctx:
    def __init__(self):
        self.security = SecurityScanner()


def _call(name, arguments):
    return asyncio.run(srv._HANDLERS[name](_Ctx(), arguments))


def test_benchmark_injection_tool_registered():
    assert "benchmark_injection" in [t.name for t in srv._TOOL_DEFS]
    assert "benchmark_injection" in srv._HANDLERS


def test_benchmark_injection_reports_measured_metrics():
    out = json.loads(_call("benchmark_injection", {}))
    assert set(out) >= {"precision", "recall", "f1", "accuracy", "tp", "fp", "tn", "fn",
                        "false_positives", "false_negatives", "total"}
    # The upgraded detector clears a high bar on the bundled corpus.
    assert out["recall"] >= 0.9
    assert out["precision"] >= 0.9
    assert out["total"] >= 20
