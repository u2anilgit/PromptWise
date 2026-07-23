import json
import uuid
import re
from pathlib import Path

from promptwise.core.model_registry import ModelRegistry

# AI-BOM minimum-elements fields (CISA/G7 "Software Bill of Materials for AI --
# Minimum Elements", verified 2026-07-23; official source
# https://www.cisa.gov/resources-tools/resources/software-bill-materials-ai-minimum-elements,
# field list summarized at
# https://windowsnews.ai/article/ai-sbom-minimum-elements-cisa-g7-baseline-for-supply-chain-transparency.417650):
#   1. supplier name / component identity   2. unique identifier
#   3. component version                    4. author
#   5. timestamp                             6. dependency relationship
#   7. cryptographic hash                    8. data provenance
#   9. model architecture & training framework
#
# promptwise.core.model_registry.ModelRegistry only genuinely tracks a subset
# of these (alias -> #2, provider -> #1, release_date -> #3/#5, family/tier ->
# #6, status). Fields it does NOT track (hash, data provenance, architecture)
# are simply omitted from the emitted component -- never filled with a guess.
# Same anti-fabrication discipline as framework_map.py (P1 Task 4).


class SBOMGenerator:
    def _ai_model_components(self, registry: ModelRegistry) -> list[dict]:
        components = []
        seen: set[str] = set()
        for alias in registry.all_aliases():
            if alias in seen:
                continue
            seen.add(alias)
            components.append({
                "type": "machine-learning-model",
                "bom-ref": f"model:{alias}",
                "name": alias,
                "properties": [
                    {"name": "supplier", "value": registry.provider_of(alias)},
                    {"name": "release_date", "value": registry.release_date_of(alias)},
                    {"name": "tier", "value": registry.tier_of(alias)},
                    {"name": "status", "value": registry.status(alias)},
                ],
            })
        return components

    def generate(self, project_dir: Path, *, include_ai_models: bool = True,
                 model_registry: "ModelRegistry | None" = None) -> dict:
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

        if include_ai_models:
            registry = model_registry if model_registry is not None else ModelRegistry()
            components.extend(self._ai_model_components(registry))

        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": f"urn:uuid:{uuid.uuid4()}",
            "version": 1,
            "metadata": {"component": {"type": "application", "name": project_path.name or "project"}},
            "components": components,
        }
