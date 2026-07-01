"""Phase 6 WP6 — dynamic model + pricing resolver.

Routing resolves tier -> family -> newest *current* alias from the registry,
never a frozen id in code. Deprecated models are retained for history but never
selected. Local, stdlib + YAML, no infrastructure.
"""
import pathlib
import textwrap

import promptwise.core.router as router_mod
from promptwise.core.model_registry import ModelRegistry
from promptwise.core.router import Router

# A family with two *current* models (different release dates) plus a
# deprecated one that has the newest date of all — to prove recency alone
# never overrides the current/deprecated status.
REG = textwrap.dedent("""
schema_version: 1
families:
  fam-x: { provider: testco, tier: powerful }
models:
  - { alias: x-2, family: fam-x, status: current, release_date: "2026-06-01", price: {input_per_mtok: 10.0, output_per_mtok: 20.0} }
  - { alias: x-1, family: fam-x, status: current, release_date: "2025-01-01", price: {input_per_mtok: 8.0, output_per_mtok: 16.0} }
  - { alias: x-0, family: fam-x, status: deprecated, release_date: "2099-12-31", price: {input_per_mtok: 5.0, output_per_mtok: 10.0} }
""")


def _registry(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(REG, encoding="utf-8")
    return ModelRegistry(p)


# ── acceptance: newest current chosen; deprecated never chosen ───────────────
def test_resolver_picks_newest_current(tmp_path):
    r = _registry(tmp_path)
    assert r.resolve("powerful", "testco") == "x-2"


def test_resolver_never_selects_deprecated_even_if_newest(tmp_path):
    r = _registry(tmp_path)
    picked = r.resolve("powerful", "testco")
    assert picked != "x-0"
    assert r.is_deprecated("x-0")
    assert "x-0" not in r.all_current()


# ── acceptance: point-in-time price is per-model, never shared ───────────────
def test_price_is_point_in_time_per_model(tmp_path):
    r = _registry(tmp_path)
    assert r.price("x-1")["input_per_mtok"] == 8.0
    assert r.price("x-2")["input_per_mtok"] == 10.0  # a newer model never rewrites x-1's price


# ── acceptance: offline / missing registry falls back cleanly ────────────────
def test_missing_registry_is_empty_and_resolves_none(tmp_path):
    r = ModelRegistry(tmp_path / "does_not_exist.yaml")
    assert r.loaded is False
    assert r.resolve("powerful") is None
    assert r.all_current() == []


def test_registry_overlays_local_models_on_base(tmp_path, monkeypatch):
    # a machine-local overlay adds on-device models on top of the tracked base
    import promptwise.core.model_registry as MR
    overlay = tmp_path / "models.local.yaml"
    overlay.write_text(
        "families:\n  local: { provider: local, tier: fast }\n"
        "models:\n  - { alias: mymodel:7b, family: local, tier: fast, status: current }\n",
        encoding="utf-8")
    monkeypatch.setattr(MR, "_overlay_paths", lambda: [overlay])
    r = MR.ModelRegistry()  # default base (repo config) + overlay
    assert "mymodel:7b" in r.all_aliases()          # local model visible
    assert "claude-opus-4-8" in r.all_aliases()     # base cloud models still present
    assert r.resolve("fast", "local") == "mymodel:7b"


# ── acceptance: router resolves the CURRENT model, not the stale literal ─────
def test_router_resolves_current_opus_from_registry():
    # Uses the repo's real config/models.yaml. The old code hardcoded the
    # now-deprecated Opus id; routing must resolve the current family alias.
    r = Router()
    res = r.route("Design a critical production security architecture",
                  intent="analysis", stakes="high", provider="claude")
    assert res.recommended_model == "claude-opus-4-8"
    assert res.recommended_model != "claude-opus-4-7"


def test_router_fast_tier_resolves_current():
    r = Router()
    res = r.route("summarize this document", intent="summarize", stakes="low", provider="claude")
    assert res.recommended_model == "claude-haiku-4-5-20251001"


def test_router_alternatives_exclude_deprecated():
    r = Router()
    res = r.route("write a function", intent="code", stakes="high", provider="claude")
    assert "claude-opus-4-7" not in res.alternatives  # deprecated never offered


def test_router_cost_uses_registry_price_for_new_model():
    r = Router()
    res = r.route("Design a critical production security architecture",
                  intent="analysis", stakes="high", provider="claude")
    # opus current price (15/Mtok) applied even though config pricing lacks 4-8
    assert res.estimated_input_cost_usd > 0


# ── acceptance: no branded model id is hardcoded in the routing engine ───────
def test_router_source_has_no_hardcoded_model_ids():
    src = pathlib.Path(router_mod.__file__).read_text(encoding="utf-8")
    for frozen in ("claude-opus-4", "claude-haiku-4", "claude-sonnet-4", "gpt-4o", "gemini-2"):
        assert frozen not in src, f"router.py must not hardcode model id '{frozen}'"
