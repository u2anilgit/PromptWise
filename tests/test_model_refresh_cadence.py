import yaml

from promptwise.core import model_refresh


def test_interval_lands_inside_the_three_to_seven_day_window():
    for key in ("a", "b", "c", "/some/install/path", "C:\\PromptWise"):
        hours = model_refresh.refresh_interval_hours(key)
        assert 3 * 24 <= hours <= 7 * 24, (key, hours)


def test_interval_is_deterministic_for_one_install():
    assert model_refresh.refresh_interval_hours("same") == model_refresh.refresh_interval_hours("same")


def test_interval_differs_across_installs():
    seen = {model_refresh.refresh_interval_hours("install-%d" % i) for i in range(40)}
    assert len(seen) > 1, "jitter collapsed -- a whole fleet would refresh in lockstep"


def test_env_overrides_base_and_jitter(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH_DAYS", "5")
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH_JITTER", "0")
    assert model_refresh.refresh_interval_hours("anything") == 5 * 24


def test_env_override_is_still_clamped_to_the_window(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH_DAYS", "90")
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH_JITTER", "0")
    assert model_refresh.refresh_interval_hours("anything") == 7 * 24
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH_DAYS", "0")
    assert model_refresh.refresh_interval_hours("anything") == 3 * 24


def test_refresh_applies_retention_so_a_partial_fetch_keeps_old_generations(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump({
        "families": {"fam": {"provider": "p", "tier": "balanced"}},
        "models": [
            {"alias": "m-1", "family": "fam", "status": "current", "release_date": "2026-01-01"},
            {"alias": "m-2", "family": "fam", "status": "current", "release_date": "2026-04-01"},
        ],
    }), encoding="utf-8")

    def fetch_only_newest():
        return [{"alias": "m-3", "family": "fam", "status": "current",
                 "release_date": "2026-09-01"}]

    out = model_refresh.refresh(registry_path=path, state_dir=tmp_path,
                                fetch_fn=fetch_only_newest, force=True, keep_per_family=3)
    assert out["refreshed"] is True
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    statuses = {m["alias"]: m["status"] for m in data["models"]}
    assert statuses == {"m-1": "current", "m-2": "current", "m-3": "current"}


def test_refresh_adds_families_named_by_new_records(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump({"families": {}, "models": []}), encoding="utf-8")

    def fetch():
        return [{"alias": "n-1", "family": "newfam", "status": "current",
                 "release_date": "2026-09-01", "provider": "np", "tier": "fast"}]

    model_refresh.refresh(registry_path=path, state_dir=tmp_path, fetch_fn=fetch, force=True)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["families"]["newfam"] == {"provider": "np", "tier": "fast"}
    assert "provider" not in data["models"][0], "provider belongs on the family, not the row"


def test_default_fetch_returns_the_pinned_catalog_offline(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_MODEL_REFRESH", raising=False)
    rows = model_refresh._default_fetch()
    assert rows, "offline default fetch must still yield the shipped catalog"
    assert all("alias" in r and "family" in r for r in rows)


def test_refresh_still_honours_an_explicit_ttl(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump({"families": {}, "models": []}), encoding="utf-8")
    model_refresh.refresh(registry_path=path, state_dir=tmp_path,
                          fetch_fn=lambda: [{"alias": "x", "family": "f"}], force=True)
    # stamp is now fresh; a non-forced call inside the TTL must not re-fetch
    out = model_refresh.refresh(registry_path=path, state_dir=tmp_path, ttl_hours=24.0,
                                fetch_fn=lambda: [{"alias": "y", "family": "f"}],
                                force=False)
    assert out["reason"] in ("fresh", "disabled")
