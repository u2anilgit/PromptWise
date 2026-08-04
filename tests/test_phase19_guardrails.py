"""Phase 19 / candidate D -- packaging guardrails (docs/PHASE19_ROADMAP.md
19.6): the base install must stay byte-for-byte unchanged. These tests
guard the two claims made in that section: core `dependencies` untouched,
and `get_sbom` never lists the new extra's dependency unless a caller
actually points it at a manifest that names it.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The exact core dependency set as of the last pre-Phase-19 release
# (fix(deps): raise mcp dependency floor to >=2.0.0). Any change to this
# set is exactly what "byte-for-byte unchanged base install" forbids --
# a failure here means core dependencies moved and needs conscious review,
# not a silent regeneration of this list.
EXPECTED_CORE_DEPENDENCIES = {
    "mcp>=1.9,<2.0",
    "sse-starlette>=2.0,<3.0",
    "aiosqlite>=0.20",
    "aiohttp>=3.8",
    "flask>=2.0",
    "tiktoken>=0.7",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "jsonschema>=4.0",
    "SQLAlchemy>=2.0",
    "prometheus-client>=0.17",
    "Authlib>=1.2",
    "anthropic>=0.7",
    "cryptography>=42.0",
}


def _load_pyproject() -> dict:
    try:
        import tomllib
    except ImportError:  # pragma: no cover - py<3.11 fallback
        import tomli as tomllib
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def test_core_dependencies_unchanged_by_phase_19():
    data = _load_pyproject()
    core_deps = set(data["project"]["dependencies"])
    assert core_deps == EXPECTED_CORE_DEPENDENCIES


def test_embeddings_extra_is_isolated_from_dev_and_core():
    data = _load_pyproject()
    core_deps = set(data["project"]["dependencies"])
    optional = data["project"]["optional-dependencies"]
    assert "embeddings" in optional
    embeddings_deps = set(optional["embeddings"])
    assert any(d.startswith("fastembed") for d in embeddings_deps)
    # fastembed must not have leaked into core deps or the dev extra.
    assert not (embeddings_deps & core_deps)
    assert not (embeddings_deps & set(optional.get("dev", [])))


def test_get_sbom_default_output_has_no_embeddings_component():
    from promptwise.core.sbom import SBOMGenerator

    sbom = SBOMGenerator().generate(REPO_ROOT, include_ai_models=False)
    names = {c.get("name", "").lower() for c in sbom["components"]}
    assert "fastembed" not in names
    assert "onnxruntime" not in names


def test_no_manifest_in_repo_declares_the_embeddings_extra():
    # get_sbom only reads requirements.txt / package.json / lockfiles, never
    # pyproject.toml's own extras -- confirms there's no accidental manifest
    # in the repo that would leak the opt-in dependency into a default SBOM.
    for manifest in ("requirements.txt", "poetry.lock", "package.json", "package-lock.json"):
        path = REPO_ROOT / manifest
        if path.exists():
            assert "fastembed" not in path.read_text(encoding="utf-8").lower()
