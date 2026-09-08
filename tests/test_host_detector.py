import pytest

from promptwise.core import host_detector
from promptwise.core.host_detector import HOST_PROVIDERS, detect_host

_ENV_VARS = ("PROMPTWISE_HOST", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CURSOR_TRACE_ID",
             "CODEX_SANDBOX", "CODEX_HOME", "GEMINI_CLI", "GEMINI_SYSTEM_MD",
             "WINDSURF_USER", "AIDER_MODEL", "GOOSE_MODE", "OPENHANDS_WORKSPACE_BASE")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    host_detector.set_client_info(None)
    yield
    host_detector.set_client_info(None)


def test_explicit_override_wins_over_everything(monkeypatch, tmp_path):
    monkeypatch.setenv("PROMPTWISE_HOST", "windsurf")
    monkeypatch.setenv("CLAUDECODE", "1")
    host_detector.set_client_info({"name": "cursor"})
    info = detect_host(repo_root=tmp_path)
    assert info.key == "windsurf"
    assert info.confidence == 1.0


def test_mcp_client_info_beats_env_and_repo(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDECODE", "1")
    (tmp_path / "GEMINI.md").write_text("x", encoding="utf-8")
    host_detector.set_client_info({"name": "Cursor", "version": "1.0"})
    info = detect_host(repo_root=tmp_path)
    assert info.key == "cursor"
    assert info.confidence == 0.95
    assert "clientInfo" in info.evidence


def test_env_var_beats_repo_scan(monkeypatch, tmp_path):
    (tmp_path / "GEMINI.md").write_text("x", encoding="utf-8")
    monkeypatch.setenv("CLAUDECODE", "1")
    info = detect_host(repo_root=tmp_path)
    assert info.key == "claude"
    assert info.confidence == 0.9


def test_repo_scan_is_the_fallback_and_is_capped(tmp_path):
    (tmp_path / "GEMINI.md").write_text("x", encoding="utf-8")
    info = detect_host(repo_root=tmp_path)
    assert info.key == "gemini"
    assert info.provider == "gemini"
    assert info.confidence <= 0.6


def test_an_empty_repo_still_yields_a_usable_provider(tmp_path):
    """agent_detector defaults an empty repo to codex; the point is that the
    caller always gets a provider it can route with, never None."""
    info = detect_host(repo_root=tmp_path)
    assert info.provider in HOST_PROVIDERS.values()


def test_client_info_is_passed_explicitly_without_touching_process_state(tmp_path):
    info = detect_host(repo_root=tmp_path, client_info={"name": "gemini-cli"})
    assert info.key == "gemini"
    assert host_detector.get_client_info() is None


def test_unusable_client_info_falls_through_to_the_next_signal(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDECODE", "1")
    host_detector.set_client_info({"name": "some-unknown-editor"})
    assert detect_host(repo_root=tmp_path).key == "claude"
    host_detector.set_client_info("not a dict")
    assert detect_host(repo_root=tmp_path).key == "claude"


def test_every_known_host_maps_to_a_provider():
    for key, provider in HOST_PROVIDERS.items():
        assert provider, "host %s has no provider" % key


def test_detect_host_never_raises_on_a_broken_repo_root():
    info = detect_host(repo_root="\x00not-a-path")
    assert info.provider
