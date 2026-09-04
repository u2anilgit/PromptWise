"""Safe dispatch smoke coverage for the complete MCP surface.

This deliberately sends empty arguments through the shared call_tool choke
point. Tools that require state or mandatory business inputs may return a
structured validation/state error; the contract under test is that every
advertised tool is dispatchable, returns JSON, and is not an unknown tool.
Stateful stores and the audit sink are redirected to pytest's temporary area.
"""
import asyncio
import json

import promptwise.core.tool_registry as registry
import promptwise.db.models as models
import promptwise.server as server


class _MemoryAudit:
    def append(self, *args, **kwargs):
        return None


def test_every_registered_tool_dispatches_safely(tmp_path, monkeypatch):
    db_path = tmp_path / "smoke.db"
    monkeypatch.setattr(models, "get_db_path", lambda: db_path)
    monkeypatch.setenv("PROMPTWISE_LEARNING_DB_PATH", str(tmp_path / "learning.db"))
    monkeypatch.setattr(registry, "_AUDIT_LOG", _MemoryAudit())

    async def run():
        results = []
        for tool in server._TOOL_DEFS:
            raw = await server.call_tool(None, tool.name, {})
            payload = json.loads(raw)
            results.append((tool.name, payload))
        return results

    results = asyncio.run(run())
    assert len(results) == 142
    assert all(not (isinstance(payload, dict) and payload.get("type") == "UnknownTool")
               for _, payload in results)
