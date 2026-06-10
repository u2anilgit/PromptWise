"""Tests for SBOMGenerator."""

from pathlib import Path
import json
from promptwise_v3.core.sbom import SBOMGenerator


def test_sbom_from_requirements_txt(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("flask>=2.0\npytest>=8.0\n")
    s = SBOMGenerator()
    result = s.generate(tmp_path)
    assert "bomFormat" in result
    assert result["bomFormat"] == "CycloneDX"
    assert result["specVersion"] == "1.5"


def test_sbom_from_package_json(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text('{"dependencies": {"express": "^4.18.0"}}')
    s = SBOMGenerator()
    result = s.generate(tmp_path)
    assert result["bomFormat"] == "CycloneDX"
    assert "components" in result


def test_sbom_no_dep_files(tmp_path):
    s = SBOMGenerator()
    result = s.generate(tmp_path)
    assert result["bomFormat"] == "CycloneDX"
