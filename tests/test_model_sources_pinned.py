from pathlib import Path

from promptwise.core.model_sources import PinnedCatalogSource, load_catalog


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "model_catalog.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_pinned_source_is_always_available_and_offline(tmp_path):
    p = _write(tmp_path, "families: {}\nmodels: []\n")
    src = PinnedCatalogSource(path=p)
    assert src.key == "pinned"
    assert src.priority == 10
    assert src.available() is True
    assert src.fetch() == []


def test_pinned_source_reads_rows_and_inherits_family_provider_and_tier(tmp_path):
    p = _write(tmp_path, """
families:
  demo-fam: {provider: demo, tier: balanced}
models:
  - alias: demo-2
    family: demo-fam
    release_date: "2026-09-01"
    context_window: 400000
    price: {input_per_mtok: 1.0, output_per_mtok: 2.0}
""")
    recs = PinnedCatalogSource(path=p).fetch()
    assert len(recs) == 1
    r = recs[0]
    assert (r.alias, r.provider, r.tier) == ("demo-2", "demo", "balanced")
    assert r.context_window == 400000
    assert r.source == "pinned"


def test_family_level_context_window_is_inherited_when_the_row_omits_it(tmp_path):
    p = _write(tmp_path, """
families:
  demo-fam: {provider: demo, tier: fast, context_window: 128000}
models:
  - alias: demo-1
    family: demo-fam
""")
    assert PinnedCatalogSource(path=p).fetch()[0].context_window == 128000


def test_missing_or_malformed_catalog_fails_open_to_empty(tmp_path):
    assert PinnedCatalogSource(path=tmp_path / "nope.yaml").fetch() == []
    bad = _write(tmp_path, "families: [this is not a mapping\n")
    assert PinnedCatalogSource(path=bad).fetch() == []


def test_rows_without_an_alias_or_family_are_skipped(tmp_path):
    p = _write(tmp_path, """
families:
  demo-fam: {provider: demo, tier: fast}
models:
  - alias: ""
    family: demo-fam
  - family: demo-fam
  - alias: orphan
  - alias: ok
    family: demo-fam
""")
    assert [r.alias for r in PinnedCatalogSource(path=p).fetch()] == ["ok"]


def test_every_shipped_family_resolves_to_at_least_one_current_model():
    """The shipped catalog is the offline guarantee: with zero network and zero
    CLIs, routing must still resolve. A declared family with no current model is
    a tier that silently returns nothing."""
    from promptwise.asset_paths import resolve_asset
    families, records = load_catalog(resolve_asset("config/model_catalog.yaml"))
    assert families, "shipped catalog declares no families"
    per_family: dict[str, int] = {}
    for r in records:
        if r.status == "current":
            per_family[r.family] = per_family.get(r.family, 0) + 1
    for fam in families:
        assert per_family.get(fam, 0) >= 1, "family " + fam + " has no current model"


def test_every_shipped_provider_carries_at_least_two_generations():
    """The 'keep 2-3 previous models' contract, asserted where it is actually
    achievable. Some families genuinely have one live generation (Claude Haiku),
    so the guarantee is stated per provider rather than per family."""
    from promptwise.asset_paths import resolve_asset
    _families, records = load_catalog(resolve_asset("config/model_catalog.yaml"))
    per_provider: dict[str, int] = {}
    for r in records:
        if r.status == "current" and r.provider:
            per_provider[r.provider] = per_provider.get(r.provider, 0) + 1
    assert per_provider, "shipped catalog declares no providers"
    for provider, count in per_provider.items():
        assert count >= 2, "provider " + provider + " has < 2 current models"


def test_every_shipped_family_declares_a_provider_and_tier():
    """A family without a provider is undiscoverable by host-scoped routing, and
    one without a tier can never be resolved by Router.route()."""
    from promptwise.asset_paths import resolve_asset
    families, _ = load_catalog(resolve_asset("config/model_catalog.yaml"))
    for name, meta in families.items():
        assert meta.get("provider"), "family " + name + " has no provider"
        assert meta.get("tier"), "family " + name + " has no tier"
