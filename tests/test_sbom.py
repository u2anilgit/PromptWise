"""Task 7 (P1) — AI-BOM minimum-elements field coverage for get_sbom.

get_sbom previously only emitted CycloneDX ``library`` components for code
dependencies (requirements.txt/package.json/lockfiles) -- zero test coverage
existed for SBOMGenerator before this task, a pre-existing gap this also
closes. Fields below are drawn from the CISA/G7 "Software Bill of Materials
for AI - Minimum Elements" guidance (verified 2026-07-23, summarized at
https://windowsnews.ai/article/ai-sbom-minimum-elements-cisa-g7-baseline-for-supply-chain-transparency.417650,
official source https://www.cisa.gov/resources-tools/resources/software-bill-materials-ai-minimum-elements):
supplier/component identity, unique identifier, component version, author,
timestamp, dependency relationship, cryptographic hash, data provenance,
model architecture & training framework. This project's model_registry.py
only genuinely tracks a subset (alias, provider, tier/family, release_date,
status) -- the rest (hash, data provenance, architecture) are omitted
entirely rather than fabricated, per this project's own prior
fabricated-compliance-claim bug class.
"""
from pathlib import Path

from promptwise.core.sbom import SBOMGenerator
from promptwise.core.model_registry import ModelRegistry


def test_generate_includes_machine_learning_model_components(tmp_path):
    gen = SBOMGenerator()
    sbom = gen.generate(tmp_path)
    ml_components = [c for c in sbom["components"] if c["type"] == "machine-learning-model"]
    assert ml_components, "expected at least one machine-learning-model component from config/models.yaml"


def test_ml_component_only_has_evidenced_fields_no_fabrication(tmp_path):
    gen = SBOMGenerator()
    sbom = gen.generate(tmp_path)
    ml_components = [c for c in sbom["components"] if c["type"] == "machine-learning-model"]
    sample = ml_components[0]
    # Evidenced fields the registry actually tracks:
    assert sample["name"]
    assert "bom-ref" in sample
    props = {p["name"]: p["value"] for p in sample.get("properties", [])}
    assert "supplier" in props  # provider, e.g. "claude"
    assert "release_date" in props
    assert "tier" in props
    assert "status" in props
    # Fields the registry does NOT track must be absent, not fabricated:
    assert "cryptographic_hash" not in props
    assert "training_data_provenance" not in props
    assert "model_architecture" not in props


def test_generate_can_disable_ai_model_components(tmp_path):
    gen = SBOMGenerator()
    sbom = gen.generate(tmp_path, include_ai_models=False)
    assert not [c for c in sbom["components"] if c["type"] == "machine-learning-model"]


def test_generate_deduplicates_ai_models_by_alias(tmp_path):
    gen = SBOMGenerator()
    sbom = gen.generate(tmp_path)
    names = [c["name"] for c in sbom["components"] if c["type"] == "machine-learning-model"]
    assert len(names) == len(set(names))


def test_generate_with_empty_registry_yields_no_ml_components(tmp_path, monkeypatch):
    empty_registry_path = tmp_path / "empty_models.yaml"
    empty_registry_path.write_text("schema_version: 1\nfamilies: {}\nmodels: []\n", encoding="utf-8")
    gen = SBOMGenerator()
    sbom = gen.generate(tmp_path, model_registry=ModelRegistry(path=empty_registry_path))
    assert not [c for c in sbom["components"] if c["type"] == "machine-learning-model"]
