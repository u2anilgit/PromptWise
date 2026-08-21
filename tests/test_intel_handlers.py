import json

import pytest

import promptwise.server  # noqa: F401 -- collection-order guard, see WP1 Task 6 / WP2 Tasks 3/5/7/9 / WP4 Task 6/8 for the bug this guards against

import promptwise.handlers.intel as intel_handlers


class _FakeCtx:
    pass


@pytest.mark.asyncio
async def test_import_threat_feed_handler(tmp_path, monkeypatch):
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps({
        "type": "bundle", "id": "bundle--x",
        "objects": [{"id": "indicator--x", "type": "indicator", "name": "x", "pattern": "[x]"}],
    }), encoding="utf-8")
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    out = await intel_handlers._handle_import_threat_feed(
        _FakeCtx(), {"bundle_path": str(bundle_path), "source": "unit-test"})
    result = json.loads(out)
    assert result["imported"] == 1
    assert result["source"] == "unit-test"


@pytest.mark.asyncio
async def test_import_threat_feed_network_seam_raises_not_implemented(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    out = await intel_handlers._handle_import_threat_feed(
        _FakeCtx(), {"bundle_path": "irrelevant.json", "allow_network": True})
    result = json.loads(out)
    assert result["type"] == "NotImplementedError"


@pytest.mark.asyncio
async def test_import_threat_feed_missing_file_returns_error_object(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    out = await intel_handlers._handle_import_threat_feed(
        _FakeCtx(), {"bundle_path": "/nonexistent/bundle.json"})
    result = json.loads(out)
    assert result["type"] == "FileNotFoundError"


@pytest.mark.asyncio
async def test_correlate_threats_handler_no_match_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.security.threat_intel._default_db", lambda: tmp_path / "intel.db")
    out = await intel_handlers._handle_correlate_threats(
        _FakeCtx(), {"content": "nothing interesting"})
    result = json.loads(out)
    assert result["matches"] == []
