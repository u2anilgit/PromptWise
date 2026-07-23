"""Phase 13.5 — SBOM transitive/lockfile parsing.

SBOMGenerator read only top-level requirements.txt / package.json. It now also
parses poetry.lock and package-lock.json for transitive dependencies, tagging
each component with a resolution property (direct vs transitive).
"""
import json

from promptwise.core.sbom import SBOMGenerator


def _by_name(sbom):
    return {c["name"]: c for c in sbom["components"]}


def _resolution(component):
    for p in component.get("properties", []):
        if p.get("name") == "resolution":
            return p.get("value")
    return None


def test_requirements_marked_direct(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    comps = _by_name(SBOMGenerator().generate(tmp_path))
    assert "flask" in comps
    assert _resolution(comps["flask"]) == "direct"


def test_poetry_lock_transitive_parsed(tmp_path):
    (tmp_path / "poetry.lock").write_text(
        '[[package]]\n'
        'name = "requests"\n'
        'version = "2.31.0"\n'
        'description = "HTTP for Humans"\n\n'
        '[[package]]\n'
        'name = "urllib3"\n'
        'version = "2.0.7"\n',
        encoding="utf-8")
    comps = _by_name(SBOMGenerator().generate(tmp_path))
    assert "requests" in comps and "urllib3" in comps
    assert comps["requests"]["version"] == "2.31.0"
    assert _resolution(comps["urllib3"]) == "transitive"
    assert comps["requests"]["purl"] == "pkg:pypi/requests@2.31.0"


def test_package_lock_v3_transitive_parsed(tmp_path):
    (tmp_path / "package-lock.json").write_text(json.dumps({
        "name": "app", "lockfileVersion": 3,
        "packages": {
            "": {"name": "app", "version": "1.0.0"},
            "node_modules/left-pad": {"version": "1.3.0"},
            "node_modules/lodash": {"version": "4.17.21"},
        },
    }), encoding="utf-8")
    comps = _by_name(SBOMGenerator().generate(tmp_path))
    assert "left-pad" in comps and "lodash" in comps
    assert comps["lodash"]["purl"] == "pkg:npm/lodash@4.17.21"
    assert _resolution(comps["left-pad"]) == "transitive"


def test_package_lock_v1_dependencies_parsed(tmp_path):
    (tmp_path / "package-lock.json").write_text(json.dumps({
        "name": "app", "lockfileVersion": 1,
        "dependencies": {
            "minimist": {"version": "1.2.8"},
            "wrappy": {"version": "1.0.2", "dependencies": {
                "once": {"version": "1.4.0"}}},
        },
    }), encoding="utf-8")
    comps = _by_name(SBOMGenerator().generate(tmp_path))
    assert {"minimist", "wrappy", "once"} <= set(comps)


def test_no_duplicate_purls(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    (tmp_path / "poetry.lock").write_text(
        '[[package]]\nname = "requests"\nversion = "2.31.0"\n', encoding="utf-8")
    sbom = SBOMGenerator().generate(tmp_path)
    # machine-learning-model components (Task 7, AI-BOM coverage) use a
    # bom-ref, not a purl -- only "library" components carry one.
    purls = [c["purl"] for c in sbom["components"] if c["type"] == "library"]
    assert len(purls) == len(set(purls))
    # The direct manifest entry wins.
    comps = _by_name(sbom)
    assert _resolution(comps["requests"]) == "direct"
