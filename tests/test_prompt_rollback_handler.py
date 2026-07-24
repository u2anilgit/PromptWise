"""_handle_rollback_prompt wires the MCP tool to MemoryManager.rollback_prompt."""
import asyncio
import json
import typing

import promptwise.server as s
from promptwise.db.models import MemoryManager


def _mm(tmp_path):
    mm = MemoryManager(str(tmp_path / "mem.db"))
    asyncio.run(mm.init())
    return mm


def _ctx(mm):
    class _FakeCtx:
        memory = mm
    return typing.cast(s.ServerContext, _FakeCtx())


def test_rollback_prompt_handler_success(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Hello A", version="1.0.0"))
    asyncio.run(mm.save_prompt("greeting", "Hello B (broken)", version="2.0.0"))

    out = json.loads(asyncio.run(s._handle_rollback_prompt(_ctx(mm), {"name": "greeting", "version": "1.0.0"})))
    assert out["status"] == "rolled_back"
    assert out["restored_version"] == "1.0.0"
    assert "new_prompt_id" in out


def test_rollback_prompt_handler_missing_version(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Hello A", version="1.0.0"))

    out = json.loads(asyncio.run(s._handle_rollback_prompt(_ctx(mm), {"name": "greeting", "version": "9.9.9"})))
    assert "error" in out
