import asyncio
import json
import tempfile
from pathlib import Path
from promptwise_v2.integrations.mcp_server_v2 import list_tools_v2, call_tool_v2, build_ctx_v2

CONFIG_DIR = Path(__file__).parents[3] / "config"

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def test_tool_count_is_36():
    tools = _run(list_tools_v2())
    assert len(tools) == 36

def test_all_v1_tools_present():
    tools = _run(list_tools_v2())
    names = {t.name for t in tools}
    v1_tools = {
        "rewrite_prompt", "optimize_context", "route_request", "plan_cache",
        "batch_prompts", "summarize_thread", "get_session_stats", "compare_providers",
        "reload_config", "ping_session", "check_session_timeout", "clear_history",
        "export_stats", "auto_compact",
    }
    assert v1_tools.issubset(names)

def test_new_v2_tools_present():
    tools = _run(list_tools_v2())
    names = {t.name for t in tools}
    new_tools = {
        "security_check", "detect_role", "orchestrate_tasks",
        "monitor_budget", "validate_output", "track_roi",
        "get_memory_context", "compress_prompt", "route_for_plugin", "check_energy",
    }
    assert new_tools.issubset(names)

def test_security_check_tool_call():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "security_check", {"text": "Hello world"}))
    data = json.loads(result)
    assert "passed" in data
    assert "risk_score" in data

def test_detect_role_tool_call():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "detect_role", {"text": "Fix the Python unit test"}))
    data = json.loads(result)
    assert "role" in data
    assert "confidence" in data

def test_orchestrate_tasks_tool_call():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "orchestrate_tasks",
                               {"text": "Read file then summarize", "strategy": "fallback"}))
    data = json.loads(result)
    assert "status" in data
    assert "steps_total" in data

def test_monitor_budget_tool_call():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "monitor_budget",
                               {"used_usd": 3.0, "days_elapsed": 10}))
    data = json.loads(result)
    assert "alert_level" in data

def test_validate_output_tool_call():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "validate_output",
                               {"code": "def add(a,b): return a+b", "language": "python"}))
    data = json.loads(result)
    assert "valid" in data

def test_compress_prompt_tool_call():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "compress_prompt",
                               {"text": "Sure! The quick brown fox jumps over the lazy dog"}))
    data = json.loads(result)
    assert "compressed" in data
    assert "saving_pct" in data

def test_unknown_tool_returns_error():
    ctx = _run(build_ctx_v2(CONFIG_DIR))
    result = _run(call_tool_v2(ctx, "nonexistent_tool", {}))
    data = json.loads(result)
    assert "error" in data
