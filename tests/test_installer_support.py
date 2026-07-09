"""core/installer_support - the only testable logic behind install.sh /
install.ps1. Both scripts are intentionally thin shell orchestration (check
python, pip install -e ., optionally register the Claude Code plugin); the
one piece of real logic - idempotently merging a `promptwise` MCP server
entry into a target .mcp.json without clobbering a user's existing entries -
lives here in Python where it is unit-testable.
"""
from __future__ import annotations

import json

import pytest

from promptwise.core import installer_support as inst


def test_default_server_entry_shape():
    entry = inst.default_server_entry("/repo")
    assert entry["command"] == "python"
    assert entry["args"] == ["-m", "promptwise.server"]
    assert entry["cwd"] == "/repo"
    assert entry["env"]["PYTHONPATH"] == "/repo/src"


def test_merge_mcp_json_adds_entry_to_empty_config():
    merged = inst.merge_mcp_json({}, "/repo")
    assert "promptwise" in merged["mcpServers"]
    assert merged["mcpServers"]["promptwise"]["command"] == "python"


def test_merge_mcp_json_preserves_other_servers():
    existing = {"mcpServers": {"other-tool": {"command": "node", "args": ["server.js"]}}}
    merged = inst.merge_mcp_json(existing, "/repo")
    assert merged["mcpServers"]["other-tool"]["command"] == "node"
    assert "promptwise" in merged["mcpServers"]


def test_merge_mcp_json_does_not_clobber_existing_promptwise_entry():
    existing = {"mcpServers": {"promptwise": {"command": "python", "args": ["custom.py"], "cwd": "/elsewhere"}}}
    merged = inst.merge_mcp_json(existing, "/repo")
    # A pre-existing promptwise entry is left alone - this is a merge, not an overwrite.
    assert merged["mcpServers"]["promptwise"]["args"] == ["custom.py"]


def test_merge_mcp_json_handles_non_dict_input():
    merged = inst.merge_mcp_json(None, "/repo")
    assert "promptwise" in merged["mcpServers"]


def test_merge_mcp_json_preserves_other_top_level_keys():
    existing = {"someOtherKey": True, "mcpServers": {}}
    merged = inst.merge_mcp_json(existing, "/repo")
    assert merged["someOtherKey"] is True


def test_write_mcp_json_creates_new_file(tmp_path):
    target = tmp_path / ".mcp.json"
    merged = inst.write_mcp_json(target, "/repo")
    assert target.exists()
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert on_disk == merged
    assert "promptwise" in on_disk["mcpServers"]


def test_write_mcp_json_merges_into_existing_file(tmp_path):
    target = tmp_path / ".mcp.json"
    target.write_text(json.dumps({"mcpServers": {"other-tool": {"command": "node"}}}), encoding="utf-8")
    inst.write_mcp_json(target, "/repo")
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert "other-tool" in on_disk["mcpServers"]
    assert "promptwise" in on_disk["mcpServers"]


def test_write_mcp_json_fails_soft_on_malformed_existing_file(tmp_path):
    target = tmp_path / ".mcp.json"
    target.write_text("not valid json {{{", encoding="utf-8")
    merged = inst.write_mcp_json(target, "/repo")
    assert "promptwise" in merged["mcpServers"]


def test_write_mcp_json_creates_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "dir" / ".mcp.json"
    inst.write_mcp_json(target, "/repo")
    assert target.exists()


def test_main_cli_writes_target_and_prints_status(tmp_path, capsys):
    target = tmp_path / ".mcp.json"
    inst.main(["--mcp-json", str(target), "--project-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert "promptwise" in out.lower()
    assert target.exists()
