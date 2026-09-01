from pathlib import Path

from promptwise.core.aibom_export import to_cyclonedx_mlbom, to_spdx3_ai_profile, export_aibom


_SAMPLE_SBOM = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.5",
    "serialNumber": "urn:uuid:test",
    "version": 1,
    "metadata": {"component": {"type": "application", "name": "demo-project"}},
    "components": [
        {"type": "library", "name": "pyyaml", "version": "6.0", "purl": "pkg:pypi/pyyaml@6.0", "properties": []},
        {"type": "machine-learning-model", "bom-ref": "model:claude-sonnet-5", "name": "claude-sonnet-5",
         "properties": [{"name": "supplier", "value": "Anthropic"}, {"name": "tier", "value": "flagship"}]},
    ],
}


def test_to_cyclonedx_mlbom_keeps_only_ml_model_components():
    mlbom = to_cyclonedx_mlbom(_SAMPLE_SBOM)
    assert mlbom["bomFormat"] == "CycloneDX"
    names = [c["name"] for c in mlbom["components"]]
    assert names == ["claude-sonnet-5"]
    assert mlbom["components"][0]["type"] == "machine-learning-model"


def test_to_cyclonedx_mlbom_empty_when_no_ml_components():
    sbom = dict(_SAMPLE_SBOM, components=[_SAMPLE_SBOM["components"][0]])
    mlbom = to_cyclonedx_mlbom(sbom)
    assert mlbom["components"] == []


def test_to_spdx3_ai_profile_maps_ml_components_to_ai_package_elements():
    spdx = to_spdx3_ai_profile(_SAMPLE_SBOM)
    assert spdx["spdxVersion"] == "SPDX-3.0"
    ai_elements = [e for e in spdx["elements"] if e.get("type") == "AIPackage"]
    assert len(ai_elements) == 1
    assert ai_elements[0]["name"] == "claude-sonnet-5"
    assert ai_elements[0]["supplier"] == "Anthropic"


def test_to_spdx3_ai_profile_never_fabricates_missing_fields():
    sbom = dict(_SAMPLE_SBOM, components=[
        {"type": "machine-learning-model", "bom-ref": "model:unknown-model", "name": "unknown-model", "properties": []},
    ])
    spdx = to_spdx3_ai_profile(sbom)
    element = spdx["elements"][0]
    assert "supplier" not in element  # no fabricated value when sbom carried none


def test_export_aibom_cyclonedx_format(tmp_path):
    (tmp_path / "requirements.txt").write_text("pyyaml==6.0\n", encoding="utf-8")
    result = export_aibom(tmp_path, fmt="cyclonedx")
    assert result["bomFormat"] == "CycloneDX"


def test_export_aibom_spdx_format(tmp_path):
    (tmp_path / "requirements.txt").write_text("pyyaml==6.0\n", encoding="utf-8")
    result = export_aibom(tmp_path, fmt="spdx")
    assert result["spdxVersion"] == "SPDX-3.0"


def test_export_aibom_rejects_unknown_format(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        export_aibom(tmp_path, fmt="not-a-format")
