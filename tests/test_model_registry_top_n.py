import textwrap

from promptwise.core.model_registry import ModelRegistry

REG = textwrap.dedent("""
schema_version: 1
families:
  ff: { provider: testco, tier: fast }
  bf: { provider: testco, tier: balanced }
models:
  - { alias: bal-newest, family: bf, status: current, release_date: "2026-03-01" }
  - { alias: bal-mid, family: bf, status: current, release_date: "2026-02-01" }
  - { alias: bal-old, family: bf, status: current, release_date: "2026-01-01" }
  - { alias: bal-deprecated, family: bf, status: deprecated, release_date: "2026-04-01" }
  - { alias: fast-only, family: ff, status: current, release_date: "2026-01-01" }
""")


def _registry(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(REG, encoding="utf-8")
    return ModelRegistry(p)


def test_top_n_current_returns_newest_first(tmp_path):
    reg = _registry(tmp_path)
    assert reg.top_n_current("balanced", n=3) == ["bal-newest", "bal-mid", "bal-old"]


def test_top_n_current_excludes_deprecated(tmp_path):
    reg = _registry(tmp_path)
    shortlist = reg.top_n_current("balanced", n=5)
    assert "bal-deprecated" not in shortlist


def test_top_n_current_respects_n(tmp_path):
    reg = _registry(tmp_path)
    assert reg.top_n_current("balanced", n=2) == ["bal-newest", "bal-mid"]


def test_top_n_current_scopes_by_tier(tmp_path):
    reg = _registry(tmp_path)
    assert reg.top_n_current("fast", n=3) == ["fast-only"]


def test_top_n_current_empty_registry_returns_empty(tmp_path):
    reg = ModelRegistry(tmp_path / "missing.yaml")
    assert reg.top_n_current("balanced", n=3) == []
