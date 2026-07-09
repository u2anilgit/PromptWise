"""Content-level regression guard for the Phase F tool-registry refactor.

Loads the pre-refactor golden snapshot (captured before _TOOL_DEFS/_HANDLERS
were merged into the decorator-based registry, see
docs/superpowers/specs/2026-07-09-phase-f-tool-registry-design.md) and
asserts today's _TOOL_DEFS is equivalent in content and order. Catches a
schema pasted under the wrong handler during migration -- something the
name-only bijection test in test_tool_registry.py cannot see.
"""
import json
from pathlib import Path

import promptwise.server as s

FIXTURE = Path(__file__).parent / "fixtures" / "tool_registry_snapshot.json"


def test_tool_defs_match_golden_snapshot():
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))
    current = [
        {"name": t.name, "description": t.description, "inputSchema": t.inputSchema}
        for t in s._TOOL_DEFS
    ]
    assert current == golden
