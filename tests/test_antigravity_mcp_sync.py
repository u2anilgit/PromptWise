import json

from promptwise.core.config_emitter import sync_antigravity_mcp


def _read(tmp_path):
    return json.loads((tmp_path / ".agents" / "mcp_config.json").read_text(encoding="utf-8"))


def test_sync_antigravity_mcp_creates_config_when_absent(tmp_path):
    status = sync_antigravity_mcp(tmp_path)

    assert status == "written"
    data = _read(tmp_path)
    assert data["mcpServers"]["promptwise"]["command"] == "python"
    assert data["mcpServers"]["promptwise"]["args"] == ["-m", "promptwise.server"]


def test_sync_antigravity_mcp_is_idempotent(tmp_path):
    sync_antigravity_mcp(tmp_path)
    first = (tmp_path / ".agents" / "mcp_config.json").read_text(encoding="utf-8")

    status = sync_antigravity_mcp(tmp_path)

    assert status == "already-configured"
    second = (tmp_path / ".agents" / "mcp_config.json").read_text(encoding="utf-8")
    assert first == second


def test_sync_antigravity_mcp_merges_without_touching_other_servers(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    existing = {
        "mcpServers": {
            "some_other_tool": {"command": "node", "args": ["other.js"]},
        }
    }
    (agents_dir / "mcp_config.json").write_text(json.dumps(existing), encoding="utf-8")

    status = sync_antigravity_mcp(tmp_path)

    assert status == "updated"
    data = _read(tmp_path)
    assert data["mcpServers"]["some_other_tool"] == {"command": "node", "args": ["other.js"]}
    assert data["mcpServers"]["promptwise"]["command"] == "python"


def test_sync_antigravity_mcp_does_not_rewrite_when_already_present(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    (agents_dir / "mcp_config.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8"
    )

    sync_antigravity_mcp(tmp_path)
    dest = agents_dir / "mcp_config.json"
    before_mtime = dest.stat().st_mtime_ns

    status = sync_antigravity_mcp(tmp_path)

    assert status == "already-configured"
    assert dest.stat().st_mtime_ns == before_mtime


def test_sync_antigravity_mcp_raises_on_malformed_existing_json(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    (agents_dir / "mcp_config.json").write_text("{not valid json", encoding="utf-8")

    import pytest

    with pytest.raises(ValueError):
        sync_antigravity_mcp(tmp_path)

    # the malformed file must be left untouched, never destroyed
    assert (agents_dir / "mcp_config.json").read_text(encoding="utf-8") == "{not valid json"
