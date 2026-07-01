"""Phase 6 WP6 (online refresh) — opt-in, daily-cached, fail-open registry refresh."""
import textwrap

from promptwise.core import model_refresh as MR
from promptwise.core.model_registry import ModelRegistry

REG = textwrap.dedent("""
schema_version: 1
families:
  fam-a: { provider: testco, tier: powerful }
models:
  - { alias: a-1, family: fam-a, status: current, release_date: "2025-01-01", price: {input_per_mtok: 10.0} }
""")


def _write_reg(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(REG, encoding="utf-8")
    return p


# ── gating ───────────────────────────────────────────────────────────────────
def test_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("PROMPTWISE_MODEL_REFRESH", raising=False)
    out = MR.refresh(registry_path=_write_reg(tmp_path), state_dir=tmp_path)
    assert out["refreshed"] is False and out["reason"] == "disabled"


def test_enabled_flag_parsing(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH", "on")
    assert MR.enabled() is True
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH", "off")
    assert MR.enabled() is False


# ── merge behavior ───────────────────────────────────────────────────────────
def test_force_refresh_adds_new_and_deprecates_missing(tmp_path):
    reg = _write_reg(tmp_path)
    fetched = [
        {"alias": "a-2", "family": "fam-a", "status": "current", "release_date": "2026-06-01",
         "price": {"input_per_mtok": 12.0}},
    ]
    out = MR.refresh(registry_path=reg, state_dir=tmp_path, force=True, fetch_fn=lambda: fetched)
    assert out["refreshed"] is True
    r = ModelRegistry(reg)
    # new current model is now selected; the old one is deprecated but retained
    assert r.resolve("powerful", "testco") == "a-2"
    assert r.is_deprecated("a-1")
    assert "a-1" in r.all_aliases()  # never deleted


def test_existing_model_price_updated_in_place(tmp_path):
    reg = _write_reg(tmp_path)
    fetched = [{"alias": "a-1", "family": "fam-a", "status": "current",
                "release_date": "2025-01-01", "price": {"input_per_mtok": 99.0}}]
    MR.refresh(registry_path=reg, state_dir=tmp_path, force=True, fetch_fn=lambda: fetched)
    assert ModelRegistry(reg).price("a-1")["input_per_mtok"] == 99.0


# ── TTL cache ────────────────────────────────────────────────────────────────
def test_ttl_fresh_path_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_MODEL_REFRESH", "on")
    reg = _write_reg(tmp_path)
    fetch = lambda: [{"alias": "a-2", "family": "fam-a", "status": "current", "release_date": "2026-06-01"}]
    MR.refresh(registry_path=reg, state_dir=tmp_path, force=True, fetch_fn=fetch)  # writes stamp
    out = MR.refresh(registry_path=reg, state_dir=tmp_path, ttl_hours=24, fetch_fn=fetch)
    assert out["refreshed"] is False and out["reason"] == "fresh"


# ── fail-open ────────────────────────────────────────────────────────────────
def test_fetch_error_is_fail_open(tmp_path):
    def boom():
        raise RuntimeError("network down")
    out = MR.refresh(registry_path=_write_reg(tmp_path), state_dir=tmp_path, force=True, fetch_fn=boom)
    assert out["refreshed"] is False and "error" in out


def test_maybe_refresh_never_raises(tmp_path):
    # default (disabled) path must be a clean no-op
    assert MR.maybe_refresh(state_dir=tmp_path)["refreshed"] is False
