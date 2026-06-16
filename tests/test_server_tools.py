"""Server tool registry: expected tools present, no duplicates, schemas well-formed."""
import promptwise.server as s

NAMES = [t.name for t in s._TOOL_DEFS]

EXPECTED = [
    "route_request", "rewrite_prompt", "optimize_context", "compress_prompt",
    "plan_cache", "batch_prompts", "summarize_thread", "compare_providers",
    "plan_workflow", "add_task", "update_task", "list_tasks", "task_report",
    "validate_mermaid", "security_check", "owasp_scan", "detect_role",
]


def test_expected_tools_registered():
    missing = [n for n in EXPECTED if n not in NAMES]
    assert not missing, missing


def test_no_duplicate_tool_names():
    dups = {n for n in NAMES if NAMES.count(n) > 1}
    assert not dups, dups


def test_dropped_framework_tool_absent():
    assert "recommend_framework" not in NAMES


def test_every_tool_has_object_schema():
    for t in s._TOOL_DEFS:
        assert t.inputSchema.get("type") == "object", t.name


def test_tool_count_floor():
    assert len(s._TOOL_DEFS) >= 57
