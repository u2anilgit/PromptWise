import json
from pathlib import Path
import re

class SBOMGenerator:
    def generate(self, project_dir: Path) -> dict:
        project_path = Path(project_dir)
        components = []

        # 1. Parse requirements.txt if present
        req_file = project_path / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text(encoding="utf-8")
                matches = re.findall(r'^([a-zA-Z0-9\-_]+)==([0-9a-zA-Z\.]+)', content, re.M)
                for name, version in matches:
                    components.append({
                        "type": "library",
                        "name": name,
                        "version": version,
                        "purl": f"pkg:pypi/{name}@{version}"
                    })
            except Exception:
                pass

        # 2. Parse package.json if present
        pkg_file = project_path / "package.json"
        if pkg_file.exists():
            try:
                data = json.loads(pkg_file.read_text(encoding="utf-8"))
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                for name, version in {**deps, **dev_deps}.items():
                    clean_ver = version.lstrip("^~>=")
                    components.append({
                        "type": "library",
                        "name": name,
                        "version": clean_ver,
                        "purl": f"pkg:npm/{name}@{clean_ver}"
                    })
            except Exception:
                pass

        # 3. Construct CycloneDX 1.5 JSON
        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": "urn:uuid:5d0234b0-a352-401d-b5b1-0985a66fd721",
            "version": 1,
            "metadata": {
                "component": {
                    "type": "application",
                    "name": project_path.name or "promptwise-project",
                }
            },
            "components": components
        }
