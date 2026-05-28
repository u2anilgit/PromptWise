import asyncio
import json
from pathlib import Path
import tempfile
from promptwise_v2.core.memory_manager import MemoryManager

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

def test_log_and_retrieve():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    mm = MemoryManager(db_path)
    _run(mm.init())
    entry = _run(mm.log(session_id="s1", tool="test_tool", summary="did a thing", cost_usd=0.001))
    assert entry.session_id == "s1"
    assert entry.tool == "test_tool"

def test_get_context_by_session():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    mm = MemoryManager(db_path)
    _run(mm.init())
    _run(mm.log(session_id="s2", tool="route_request", summary="routed to sonnet", cost_usd=0.002))
    entries = _run(mm.get_context(session_id="s2"))
    assert len(entries) >= 1

def test_auto_prune_old_entries():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    mm = MemoryManager(db_path)
    _run(mm.init())
    deleted = _run(mm.prune(retention_weeks=0))
    assert isinstance(deleted, int)

def test_export_json():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    mm = MemoryManager(db_path)
    _run(mm.init())
    _run(mm.log(session_id="s3", tool="rewrite_prompt", summary="rewrote", cost_usd=0.001))
    exported = _run(mm.export_json())
    data = json.loads(exported)
    assert isinstance(data, list)
