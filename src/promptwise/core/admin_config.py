"""core.admin_config -- reads/writes config/admin.yaml: generic feature
flags (global + per-project override), and the knowledgebase's own
enabled/store_path settings. Mirrors config/policy.yaml's plain-YAML,
tracked-file convention (not gitignored -- flags and limits aren't
secrets, unlike config/dashboard_auth.yaml's credential hashes).

Both the admin MCP tools (handlers/admin.py) and the dashboard Admin tab
(dashboard/web.py) call these same functions -- one code path, two entry
points, no logic duplicated between them.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_DEFAULT_PATH = Path("config") / "admin.yaml"

_DEFAULTS = {
    "features": {},
    "project_features": {},
    "budget": {},
    "knowledgebase": {"enabled": False, "store_path": None},
}


def _resolve_path(path: Path | str | None) -> Path:
    return Path(path) if path else _DEFAULT_PATH


def load_admin_config(path: Path | str | None = None) -> dict:
    p = _resolve_path(path)
    if not p.exists():
        return {k: (dict(v) if isinstance(v, dict) else v) for k, v in _DEFAULTS.items()}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in _DEFAULTS.items()}
    for key in out:
        if key in data:
            if isinstance(out[key], dict) and isinstance(data[key], dict):
                out[key].update(data[key])
            else:
                out[key] = data[key]
    return out


def _save(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def set_feature_flag(name: str, enabled: bool, project: str | None = None,
                      path: Path | str | None = None) -> dict:
    p = _resolve_path(path)
    cfg = load_admin_config(p)
    if project:
        cfg["project_features"].setdefault(project, {})[name] = enabled
    else:
        cfg["features"][name] = enabled
    _save(cfg, p)
    return cfg


def get_admin_settings(path: Path | str | None = None) -> dict:
    return load_admin_config(path)
