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
    price_x1 = r.price("x-1")
    price_x2 = r.price("x-2")
    assert price_x1 is not None and price_x2 is not None
    assert price_x1["input_per_mtok"] == 8.0
    assert price_x2["input_per_mtok"] == 10.0  # a newer model never rewrites x-1's price


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


def test_router_alternatives_exclude_deprecated(tmp_path):
    reg = _registry(tmp_path)
    r = Router(registry=reg)
    res = r.route("write a function", intent="code", stakes="high", provider="testco")
    assert "x-0" not in res.alternatives  # deprecated never offered
    assert "x-1" in res.alternatives  # a second current model in the same
    # family/tier IS offered as an alternative -- the registry intentionally
    # keeps the previous-gen model "current" alongside the newest one so
    # routing/cost-optimization can pick among active models, not just latest


def test_cheapest_current_picks_lowest_price_among_current(tmp_path):
    reg = _registry(tmp_path)
    r = Router(registry=reg)
    assert r._cheapest_current("powerful", "testco") == "x-1"  # 8.0 < 10.0, x-0 is deprecated


def test_cheapest_current_none_when_tier_empty(tmp_path):
    reg = _registry(tmp_path)
    r = Router(registry=reg)
    assert r._cheapest_current("fast", "testco") is None  # fam-x is powerful-only


def test_pressure_pct_zero_when_no_signals_supplied():
    r = Router()
    pct = r._pressure_pct(cap=None, provider_spend_usd=None,
                           monthly_budget_usd=None, days_elapsed_in_month=None)
    assert pct == 0.0


def test_pressure_pct_from_provider_cap():
    r = Router()
    pct = r._pressure_pct(cap=50.0, provider_spend_usd=40.0,
                           monthly_budget_usd=None, days_elapsed_in_month=None)
    assert pct == 80.0


def test_pressure_pct_from_monthly_pace():
    r = Router()
    # projected = 90 / 30 * 30 = 90; 90 / 100 * 100 = 90.0
    pct = r._pressure_pct(cap=None, provider_spend_usd=90.0,
                           monthly_budget_usd=100.0, days_elapsed_in_month=30)
    assert pct == 90.0


def test_pressure_pct_is_the_higher_of_the_two_signals():
    r = Router()
    # provider cap pressure: 90/200*100 = 45.0; monthly pace pressure:
    # (90/30*30)/100*100 = 90.0 -- the higher one (monthly pace) wins
    pct = r._pressure_pct(cap=200.0, provider_spend_usd=90.0,
                           monthly_budget_usd=100.0, days_elapsed_in_month=30)
    assert pct == 90.0


def test_route_below_80pct_pressure_picks_newest_unchanged(tmp_path):
    reg = _registry(tmp_path)
    r = Router(registry=reg)
    res = r.route("Design a critical production security architecture", intent="analysis",
                  stakes="high", provider="testco",
                  monthly_budget_usd=100.0, days_elapsed_in_month=30, provider_spend_usd=10.0)
    # projected = 10/30*30 = 10 -> 10% pressure, well under 80
    assert res.recommended_model == "x-2"
    assert "cost pressure" not in res.reason


def test_route_80_to_99pct_pressure_picks_cheaper_same_tier(tmp_path):
    reg = _registry(tmp_path)
    r = Router(registry=reg)
    res = r.route("Design a critical production security architecture", intent="analysis",
                  stakes="high", provider="testco",
                  monthly_budget_usd=100.0, days_elapsed_in_month=30, provider_spend_usd=90.0)
    # projected = 90/30*30 = 90 -> 90% pressure, in [80, 100)
    assert res.recommended_model == "x-1"  # cheaper current model in the same "powerful" tier
    assert "cost pressure" in res.reason
    assert "90.0%" in res.reason
    assert res.monthly_budget_capped is False  # still under the 100% hard cap


def test_route_100pct_pressure_still_hard_collapses_to_fast(tmp_path):
    reg = _registry(tmp_path)
    r = Router(registry=reg)
    res = r.route("Design a critical production security architecture", intent="analysis",
                  stakes="high", provider="testco",
                  monthly_budget_usd=100.0, days_elapsed_in_month=30, provider_spend_usd=100.0)
    # projected = 100/30*30 = 100 -> 100% pressure -- unchanged existing hard-cap behavior
    assert res.monthly_budget_capped is True
    # fam-x only has a "powerful" tier, so the fast-tier fallback resolves via
    # config default rather than the registry -- what matters here is that the
    # staged 80-99% swap did NOT override the existing hard collapse.
    assert res.recommended_model != "x-1"
    assert res.recommended_model != "x-2"


def test_route_no_budget_params_never_triggers_cost_switch():
    r = Router()
    res = r.route("Design a critical production security architecture",
                  intent="analysis", stakes="high", provider="claude")
    assert "cost pressure" not in res.reason


def test_resolve_model_below_80_returns_balanced_unchanged():
    r = Router()
    assert r.resolve_model("some_skill", budget_pct=50.0) == r._tier_model("balanced")


def test_resolve_model_95_and_above_returns_fast_unchanged():
    r = Router()
    assert r.resolve_model("some_skill", budget_pct=95.0) == r._tier_model("fast")


def test_resolve_model_80_to_95_prefers_cheaper_balanced_model(tmp_path):
    reg = _registry(tmp_path)
    r = Router(registry=reg)
    # fam-x is a "powerful"-tier family, so "balanced" has nothing in this
    # synthetic registry -- _cheapest_current returns None and the method
    # must fall back to the plain _tier_model("balanced") result, proving
    # the fallback path (not just the happy path) is exercised.
    assert r.resolve_model("some_skill", budget_pct=85.0) == r._tier_model("balanced")


_BALANCED_REG = textwrap.dedent("""
schema_version: 1
families:
  fam-y: { provider: testco, tier: balanced }
models:
  - { alias: y-new, family: fam-y, status: current, release_date: "2026-06-01", price: {input_per_mtok: 10.0, output_per_mtok: 20.0} }
  - { alias: y-old, family: fam-y, status: current, release_date: "2025-01-01", price: {input_per_mtok: 6.0, output_per_mtok: 12.0} }
""")


def test_resolve_model_80_to_95_uses_cheapest_current_when_available(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(_BALANCED_REG, encoding="utf-8")
    r = Router(registry=ModelRegistry(p))
    result = r.resolve_model("some_skill", budget_pct=85.0)
    assert result == "y-old"  # 6.0 < 10.0, cheaper current model wins over the newest


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
