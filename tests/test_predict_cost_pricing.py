"""Phase 14 WP14.1 -- predict_cost pricing-drift fix.

``BudgetGuardian.predict_cost`` hardcoded its own tier -> price table, duplicating
``config/models.yaml`` / ``config/promptwise.yaml`` and silently drifting out of
sync (see ``docs/GAP_ANALYSIS_2026-07.md`` section 3, "Bug" note -- haiku's
hardcoded rate was 0.8/4.0 per Mtok vs. the registry's live 1.0/5.0). This phase
makes ``predict_cost`` read the SAME registry-first, config-fallback chain
``core/router.py``'s ``_input_rate`` already uses, so the two engines can never
disagree again.
"""
import pathlib
import textwrap

import promptwise.plugins.budget as budget_mod
from promptwise.core.model_registry import ModelRegistry
from promptwise.plugins.budget import BudgetGuardian


def _registry(path, yaml_text):
    path.write_text(textwrap.dedent(yaml_text), encoding="utf-8")
    return ModelRegistry(path)


def test_predict_cost_uses_registry_price_not_a_hardcoded_dict(tmp_path):
    reg = _registry(tmp_path / "models.yaml", """
        schema_version: 1
        families:
          fam-x: { provider: claude, tier: fast }
        models:
          - { alias: test-model, family: fam-x, status: current, release_date: "2026-01-01",
              price: { input_per_mtok: 111.0, output_per_mtok: 222.0 } }
    """)
    g = BudgetGuardian(registry=reg)
    r = g.predict_cost("a" * 4000, model="test-model")  # 1000 input tokens -> 2000 output
    expected = round(1000 * 111.0 / 1_000_000 + 2000 * 222.0 / 1_000_000, 8)
    assert r["estimated_cost_usd"] == expected


def test_predict_cost_reflects_registry_price_changes_across_instances(tmp_path):
    reg_cheap = _registry(tmp_path / "cheap.yaml", """
        schema_version: 1
        families:
          fam-x: { provider: claude, tier: fast }
        models:
          - { alias: same-alias, family: fam-x, status: current, release_date: "2026-01-01",
              price: { input_per_mtok: 1.0, output_per_mtok: 2.0 } }
    """)
    reg_pricey = _registry(tmp_path / "pricey.yaml", """
        schema_version: 1
        families:
          fam-x: { provider: claude, tier: fast }
        models:
          - { alias: same-alias, family: fam-x, status: current, release_date: "2026-01-01",
              price: { input_per_mtok: 50.0, output_per_mtok: 100.0 } }
    """)
    g_cheap = BudgetGuardian(registry=reg_cheap)
    g_pricey = BudgetGuardian(registry=reg_pricey)
    c_cheap = g_cheap.predict_cost("a" * 4000, model="same-alias")["estimated_cost_usd"]
    c_pricey = g_pricey.predict_cost("a" * 4000, model="same-alias")["estimated_cost_usd"]
    assert c_cheap != c_pricey
    assert c_pricey > c_cheap


def test_predict_cost_haiku_matches_live_registry_price_not_stale_hardcode():
    # Real config/models.yaml. The old hardcoded dict had haiku input=0.8/output=4.0,
    # stale against the registry's current 1.0/5.0.
    g = BudgetGuardian()
    r = g.predict_cost("x" * 4000, model="claude-haiku-4-5-20251001")
    expected = round(1000 * 1.0 / 1_000_000 + 2000 * 5.0 / 1_000_000, 8)
    assert r["estimated_cost_usd"] == expected


def test_predict_cost_accepts_bare_tier_word_for_backward_compat():
    g = BudgetGuardian()
    r = g.predict_cost("hello world", model="haiku")
    assert r["estimated_cost_usd"] > 0
    assert r["model"] == "haiku"  # echoes caller's input, not the resolved alias


def test_budget_module_has_no_hardcoded_pricing_table():
    src = pathlib.Path(budget_mod.__file__).read_text(encoding="utf-8")
    assert "pricing = {" not in src, (
        "predict_cost must read live pricing from the model registry, "
        "not a local hardcoded per-tier dict"
    )
