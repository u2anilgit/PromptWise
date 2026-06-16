import json
import uuid
import re
from pathlib import Path


class SBOMGenerator:
    def generate(self, project_dir: Path) -> dict:
        project_path = Path(project_dir)
        components = []

        req_file = project_path / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text(encoding="utf-8")
                matches = re.findall(r'^([a-zA-Z0-9\-_]+)==([0-9a-zA-Z\.]+)', content, re.M)
                for name, version in matches:
                    components.append({"type": "library", "name": name, "version": version, "purl": f"pkg:pypi/{name}@{version}"})
            except Exception:
                pass

        pkg_file = project_path / "package.json"
        if pkg_file.exists():
            try:
                data = json.loads(pkg_file.read_text(encoding="utf-8"))
                for name, version in {**data.get("dependencies", {}), **data.get("devDependencies", {})}.items():
                    components.append({"type": "library", "name": name, "version": version.lstrip("^~>="), "purl": f"pkg:npm/{name}@{version.lstrip('^~>=')}"})
            except Exception:
                pass

        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": f"urn:uuid:{uuid.uuid4()}",
            "version": 1,
            "metadata": {"component": {"type": "application", "name": project_path.name or "project"}},
            "components": components,
        }
