import json
from pathlib import Path

from promptwise.core.doctor import bootstrap


def test_bootstrap_default_does_not_sync_agents(tmp_path):
    result = bootstrap(cwd=tmp_path)
    assert result["ok"] is True
    assert "synced_agents" not in result
    assert "agent_files" not in result
    # only .promptwise/ should exist -- no agent rule files written
    entries = {p.name for p in tmp_path.iterdir()}
    assert entries == {".promptwise"}


def test_bootstrap_sync_agents_writes_detected_hosts(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# claude rules\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# codex rules\n", encoding="utf-8")

    result = bootstrap(cwd=tmp_path, sync_agents=True)

    assert result["ok"] is True
    assert "claude" in result["synced_agents"]
    assert "codex" in result["synced_agents"]
    assert isinstance(result["agent_files"], dict)
    assert len(result["agent_files"]) > 0
    assert "agent_sync_error" not in result


def test_bootstrap_sync_agents_failure_is_non_fatal(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("detector exploded")

    monkeypatch.setattr("promptwise.core.agent_detector.detect_agents", boom)

    result = bootstrap(cwd=tmp_path, sync_agents=True)

    assert result["ok"] is True
    assert "agent_sync_error" in result
    assert "detector exploded" in result["agent_sync_error"]
    assert "synced_agents" not in result
