"""Server tool registry: expected tools present, no duplicates, schemas well-formed."""
import asyncio
import json
import typing

import promptwise.server as s

NAMES = [t.name for t in s._TOOL_DEFS]

# None is a valid stand-in for ctx in these dispatch tests: the tools exercised
# here (detect_agents, orchestrate_tasks, shard_doc, ...) never read ctx. Cast
# documents that gap instead of building a real 23-field ServerContext.
_CTX = typing.cast(s.ServerContext, None)

AGILE_TOOLS = [
    "shard_doc", "draft_story", "run_quality_gate", "check_policy",
    "record_audit", "export_audit", "sync_agent_config",
]

CONFIG_COMPILER_TOOLS = [
    "detect_agents", "build_context_model", "propose_agent_config", "lint_agent_config",
]

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
    assert len(s._TOOL_DEFS) >= 69


def test_agile_governance_tools_registered():
    missing = [n for n in AGILE_TOOLS if n not in NAMES]
    assert not missing, missing


def test_config_compiler_tools_registered():
    missing = [n for n in CONFIG_COMPILER_TOOLS if n not in NAMES]
    assert not missing, missing


def test_detect_agents_dispatch(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# x", encoding="utf-8")
    out = asyncio.run(s.call_tool(_CTX, "detect_agents", {"repo_root": str(tmp_path)}))
    assert "claude" in json.loads(out)["targets"]


def test_propose_agent_config_writes_nothing(tmp_path):
    out = asyncio.run(s.call_tool(_CTX, "propose_agent_config",
                                  {"project": "acme", "policy_summary": ["x"],
                                   "repo_root": str(tmp_path), "targets": ["claude"]}))
    res = json.loads(out)
    assert res["CLAUDE.md"]["status"] == "create"
    assert not (tmp_path / "CLAUDE.md").exists()


def test_orchestrate_emits_wave_plan_for_structured_tasks():
    tasks = [
        {"id": "a"},
        {"id": "b", "depends_on": ["a"]},
        {"id": "c", "depends_on": ["a"]},
        {"id": "d", "depends_on": ["b", "c"]},
    ]
    out = json.loads(asyncio.run(s.call_tool(_CTX, "orchestrate_tasks", {"text": "", "tasks": tasks})))
    assert out["mode"] == "plan"
    assert out["waves"][0] == ["a"]
    assert set(out["waves"][1]) == {"b", "c"}
    assert not out["has_cycle"]


def test_orchestrate_plan_flags_cycle():
    tasks = [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]
    out = json.loads(asyncio.run(s.call_tool(_CTX, "orchestrate_tasks", {"text": "", "tasks": tasks})))
    assert out["has_cycle"] and out["cycle"] == ["a", "b"]


def test_shard_doc_dispatch():
    # these tools ignore ctx -> safe to dispatch with ctx=None
    out = asyncio.run(s.call_tool(_CTX, "shard_doc", {"markdown": "# A\nx\n## B\ny\n"}))
    shards = json.loads(out)
    assert [sh["title"] for sh in shards] == ["A", "B"]


def test_quality_gate_dispatch():
    out = asyncio.run(s.call_tool(_CTX, "run_quality_gate",
                                  {"story_id": "S1", "findings": [{"severity": "high"}]}))
    assert json.loads(out)["decision"] == "FAIL"


import pytest


@pytest.mark.asyncio
async def test_generate_ed25519_keypair_tool():
    from promptwise.handlers.compliance_export import _handle_generate_ed25519_keypair
    result = json.loads(await _handle_generate_ed25519_keypair(_CTX, {}))
    assert set(result) == {"private_key", "public_key"}
    assert len(bytes.fromhex(result["private_key"])) == 32
    assert len(bytes.fromhex(result["public_key"])) == 32


@pytest.mark.asyncio
async def test_export_compliance_bundle_tool_sign_alg_ed25519(monkeypatch):
    from promptwise.core.compliance_export import generate_ed25519_keypair, ENV_KEY_ED25519
    from promptwise.handlers.compliance_export import _handle_export_compliance_bundle
    pair = generate_ed25519_keypair()
    monkeypatch.setenv(ENV_KEY_ED25519, pair["private_key"])
    result = json.loads(await _handle_export_compliance_bundle(_CTX, {"sign_alg": "ed25519"}))
    assert result["signed"] is True
    assert result["signature"]["alg"] == "Ed25519"


def test_sync_agent_config_dispatch(tmp_path):
    out = asyncio.run(s.call_tool(_CTX, "sync_agent_config",
                                  {"project": "acme", "policy_summary": ["Budget $5/day"],
                                   "packs": ["agile-sm"], "repo_root": str(tmp_path),
                                   "targets": ["claude", "cursor"]}))
    written = json.loads(out)["written"]
    assert set(written) == {"CLAUDE.md", ".cursor/rules/promptwise.mdc"}
    assert "Budget $5/day" in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
