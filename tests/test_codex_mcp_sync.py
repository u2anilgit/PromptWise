from promptwise.core.config_emitter import sync_codex_mcp


def test_sync_codex_mcp_creates_config_when_absent(tmp_path):
    status = sync_codex_mcp(tmp_path)

    assert status == "written"
    content = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.promptwise]" in content
    assert 'command = "python"' in content
    assert '"-m", "promptwise.server"' in content


def test_sync_codex_mcp_is_idempotent(tmp_path):
    sync_codex_mcp(tmp_path)
    first = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")

    status = sync_codex_mcp(tmp_path)

    assert status == "already-configured"
    second = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert first == second


def test_sync_codex_mcp_appends_without_touching_existing_content(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    existing = (
        '[mcp_servers.some_other_tool]\n'
        'command = "node"\n'
        'args = ["other.js"]\n'
    )
    (codex_dir / "config.toml").write_text(existing, encoding="utf-8")

    status = sync_codex_mcp(tmp_path)

    assert status == "appended"
    content = (codex_dir / "config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.some_other_tool]" in content
    assert 'command = "node"' in content
    assert "[mcp_servers.promptwise]" in content


def test_sync_codex_mcp_does_not_duplicate_on_repeat_append(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        '[mcp_servers.some_other_tool]\ncommand = "node"\n', encoding="utf-8"
    )

    sync_codex_mcp(tmp_path)
    status = sync_codex_mcp(tmp_path)

    assert status == "already-configured"
    content = (codex_dir / "config.toml").read_text(encoding="utf-8")
    assert content.count("[mcp_servers.promptwise]") == 1
