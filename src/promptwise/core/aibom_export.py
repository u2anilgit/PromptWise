"""core.aibom_export -- reformat existing SBOM/model-registry data into
AI-BOM outputs (CycloneDX ML-BOM subset, SPDX 3.0 AI Profile). No new
data collection: this module only reshapes what core/sbom.py's
SBOMGenerator already produces from ModelRegistry -- same
anti-fabrication discipline (see sbom.py:8-23), never guesses a field the
underlying data doesn't carry.

See docs/superpowers/specs/2026-08-31-promptwise-enterprise-identity-phase1-design.md
(Components table: AIBOM export).
"""
from __future__ import annotations

from pathlib import Path

_ML_MODEL_TYPE = "machine-learning-model"


def _ml_components(sbom: dict) -> list[dict]:
    return [c for c in sbom.get("components", []) if c.get("type") == _ML_MODEL_TYPE]


def to_cyclonedx_mlbom(sbom: dict) -> dict:
    """CycloneDX ML-BOM: same envelope as the full SBOM, components
    filtered to machine-learning-model entries only."""
    return {
        "bomFormat": sbom.get("bomFormat", "CycloneDX"),
        "specVersion": sbom.get("specVersion", "1.5"),
        "serialNumber": sbom.get("serialNumber", ""),
        "version": sbom.get("version", 1),
        "metadata": sbom.get("metadata", {}),
        "components": _ml_components(sbom),
    }


def to_spdx3_ai_profile(sbom: dict) -> dict:
    """SPDX 3.0 AI Profile: each machine-learning-model component becomes
    an AIPackage element. Only fields actually present in the source
    component's `properties` are copied -- an absent property is simply
    absent from the output element, never fabricated."""
    elements = []
    for comp in _ml_components(sbom):
        props = {p["name"]: p["value"] for p in comp.get("properties", []) if "name" in p and "value" in p}
        element: dict = {
            "type": "AIPackage",
            "spdxId": comp.get("bom-ref", f"AIPackage-{comp.get('name', 'unknown')}"),
            "name": comp.get("name", ""),
        }
        for key in ("supplier", "release_date", "tier", "status"):
            if key in props:
                element[key] = props[key]
        elements.append(element)
    return {
        "spdxVersion": "SPDX-3.0",
        "dataLicense": "CC0-1.0",
        "name": sbom.get("metadata", {}).get("component", {}).get("name", "project"),
        "elements": elements,
    }


def export_aibom(project_path: Path | str, fmt: str = "cyclonedx") -> dict:
    """One-shot: generate the underlying SBOM, then reshape to the
    requested AI-BOM format. fmt: "cyclonedx" (default) | "spdx"."""
    if fmt not in ("cyclonedx", "spdx"):
        raise ValueError(f"unknown AI-BOM format: {fmt!r} (expected 'cyclonedx' or 'spdx')")
    from promptwise.core.sbom import SBOMGenerator
    sbom = SBOMGenerator().generate(Path(project_path))
    return to_cyclonedx_mlbom(sbom) if fmt == "cyclonedx" else to_spdx3_ai_profile(sbom)
