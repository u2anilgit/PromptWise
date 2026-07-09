import json
import uuid
import re
from pathlib import Path


class SBOMGenerator:
    def generate(self, project_dir: Path) -> dict:
        project_path = Path(project_dir)
        components: list[dict] = []
        seen_purls: set[str] = set()

        def _add(name: str, version: str, ecosystem: str, resolution: str) -> None:
            if not name or not version:
                return
            purl = f"pkg:{ecosystem}/{name}@{version}"
            if purl in seen_purls:
                return  # a package resolved once — the first (direct) entry wins
            seen_purls.add(purl)
            components.append({
                "type": "library", "name": name, "version": version, "purl": purl,
                "properties": [{"name": "resolution", "value": resolution}],
            })

        # ── direct dependencies (top-level manifests) ───────────────────────
        req_file = project_path / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text(encoding="utf-8")
                for name, version in re.findall(r'^([a-zA-Z0-9\-_]+)==([0-9a-zA-Z\.]+)', content, re.M):
                    _add(name, version, "pypi", "direct")
            except Exception:
                pass

        pkg_file = project_path / "package.json"
        if pkg_file.exists():
            try:
                data = json.loads(pkg_file.read_text(encoding="utf-8"))
                for name, version in {**data.get("dependencies", {}), **data.get("devDependencies", {})}.items():
                    _add(name, str(version).lstrip("^~>="), "npm", "direct")
            except Exception:
                pass

        # ── transitive dependencies (lockfiles) ─────────────────────────────
        poetry_lock = project_path / "poetry.lock"
        if poetry_lock.exists():
            try:
                content = poetry_lock.read_text(encoding="utf-8")
                for block in content.split("[[package]]")[1:]:
                    nm = re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', block)
                    ver = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', block)
                    if nm and ver:
                        _add(nm.group(1), ver.group(1), "pypi", "transitive")
            except Exception:
                pass

        npm_lock = project_path / "package-lock.json"
        if npm_lock.exists():
            try:
                data = json.loads(npm_lock.read_text(encoding="utf-8"))
                packages = data.get("packages")
                if isinstance(packages, dict):  # lockfileVersion 2/3
                    for path, meta in packages.items():
                        if not path or not isinstance(meta, dict):
                            continue  # "" is the root project itself
                        name = meta.get("name") or path.split("node_modules/")[-1]
                        _add(name, str(meta.get("version", "")), "npm", "transitive")
                else:  # lockfileVersion 1 — nested dependencies tree
                    def _walk(deps: dict) -> None:
                        for name, meta in (deps or {}).items():
                            if isinstance(meta, dict):
                                _add(name, str(meta.get("version", "")), "npm", "transitive")
                                _walk(meta.get("dependencies", {}))
                    _walk(data.get("dependencies", {}))
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
