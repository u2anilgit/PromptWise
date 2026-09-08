import json

from promptwise.core.model_sources import ApiModelSource, build_default_registry

BODY = json.dumps({"data": [
    {"id": "widget-9", "created_at": "2026-09-01"},
    {"id": "widget-8", "created_at": "2026-03-01"},
]})


def _src(**kw):
    kw.setdefault("key", "widget")
    kw.setdefault("url", "https://example.invalid/v1/models")
    kw.setdefault("auth_env", "WIDGET_API_KEY")
    kw.setdefault("field_map", {"alias": "id", "release_date": "created_at"})
    kw.setdefault("family_map", {"widget": {"family": "widget-fam", "provider": "widget", "tier": "balanced"}})
    kw.setdefault("opener", lambda url, headers, timeout: BODY)
    return ApiModelSource(**kw)


def test_api_source_is_unavailable_without_the_global_refresh_flag(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_MODEL_REFRESH", raising=False)
    monkeypatch.setenv("WIDGET_API_KEY", "sk-test")
    assert _src().available() is False


def test_api_source_is_unavailable_without_its_credential(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH", "on")
    monkeypatch.delenv("WIDGET_API_KEY", raising=False)
    assert _src().available() is False


def test_api_source_parses_a_listing_when_both_gates_are_open(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH", "on")
    monkeypatch.setenv("WIDGET_API_KEY", "sk-test")
    recs = sorted(_src().fetch(), key=lambda r: r.alias)
    assert [r.alias for r in recs] == ["widget-8", "widget-9"]
    assert recs[0].provider == "widget"
    assert recs[1].release_date == "2026-09-01"
    assert recs[0].source == "widget"


def test_the_credential_is_substituted_into_headers_and_never_logged(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH", "on")
    monkeypatch.setenv("WIDGET_API_KEY", "sk-secret")
    captured = {}

    def opener(url, headers, timeout):
        captured.update(headers)
        return BODY

    _src(headers={"Authorization": "Bearer ${TOKEN}"}, opener=opener).fetch()
    assert captured["Authorization"] == "Bearer sk-secret"


def test_api_source_network_failure_fails_open(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH", "on")
    monkeypatch.setenv("WIDGET_API_KEY", "sk-test")

    def boom(url, headers, timeout):
        raise OSError("connection refused")

    assert _src(opener=boom).fetch() == []


def test_api_source_malformed_payload_fails_open(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH", "on")
    monkeypatch.setenv("WIDGET_API_KEY", "sk-test")
    assert _src(opener=lambda u, h, t: "not json at all").fetch() == []
    assert _src(opener=lambda u, h, t: json.dumps({"data": "not a list"})).fetch() == []


def test_build_default_registry_always_includes_pinned_and_local(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_MODEL_REFRESH", raising=False)
    reg = build_default_registry()
    keys = {s.key for s in reg.sources}
    assert "pinned" in keys
    assert "local" in keys
    # offline: fetch_all still returns the shipped catalog, and never raises
    assert reg.fetch_all()


def test_build_default_registry_survives_a_missing_config(tmp_path):
    reg = build_default_registry(config_path=tmp_path / "nope.yaml")
    assert {s.key for s in reg.sources} == {"pinned", "local"}
