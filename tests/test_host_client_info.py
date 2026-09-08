import pytest

from promptwise.core import host_detector
from promptwise.server import _client_info_from_session, capture_client_info

_ENV_VARS = ("PROMPTWISE_HOST", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CURSOR_TRACE_ID",
             "CODEX_SANDBOX", "CODEX_HOME", "GEMINI_CLI", "GEMINI_SYSTEM_MD")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    host_detector.set_client_info(None)
    yield
    host_detector.set_client_info(None)


def test_capture_client_info_sets_the_detected_host(tmp_path):
    capture_client_info({"name": "gemini-cli", "version": "2.0"})
    info = host_detector.detect_host(repo_root=tmp_path)
    assert info.key == "gemini"
    assert info.provider == "gemini"


def test_capture_client_info_tolerates_garbage(tmp_path):
    capture_client_info(None)
    capture_client_info("not a dict")
    capture_client_info({"no_name": True})
    assert host_detector.detect_host(repo_root=tmp_path).provider


class _Client:
    def model_dump(self):
        return {"name": "cursor", "version": "3.1"}


class _Session:
    def __init__(self, client):
        self.client_params = type("P", (), {"clientInfo": client})()


def test_client_info_is_read_off_a_pydantic_style_session():
    assert _client_info_from_session(_Session(_Client())) == {"name": "cursor", "version": "3.1"}


def test_client_info_falls_back_to_plain_attributes():
    plain = type("C", (), {"name": "codex", "version": "1.0"})()
    assert _client_info_from_session(_Session(plain)) == {"name": "codex", "version": "1.0"}


def test_client_info_returns_none_for_an_unusable_session():
    assert _client_info_from_session(None) is None
    assert _client_info_from_session(_Session(None)) is None
    assert _client_info_from_session(object()) is None
