"""Portable discovery of PromptWise runtime assets.

The source checkout keeps configuration, skill packs, and corpora at the
repository root.  Wheels cannot rely on that layout, so the same assets are
bundled below :mod:`promptwise` and used as a deterministic fallback.
"""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ASSET_ROOT = Path(__file__).resolve().parent / "_assets"
ROOT_ENV = "PROMPTWISE_ROOT"
CONFIG_ENV = "PROMPTWISE_CONFIG_DIR"


def _has_runtime_layout(path: Path) -> bool:
    return (path / "config" / "promptwise.yaml").is_file() and (
        (path / "skill_packs").is_dir() or (path / "corpus").is_dir()
    )


def _ancestors(start: Path):
    current = start.expanduser().resolve()
    yield current
    yield from current.parents


def find_project_root(start: str | Path | None = None) -> Path | None:
    """Find a checkout root from an explicit root or the current directory."""
    raw = os.environ.get(ROOT_ENV)
    if raw:
        candidate = Path(raw).expanduser().resolve()
        if _has_runtime_layout(candidate):
            return candidate

    bases = [Path(start)] if start is not None else [Path.cwd()]
    # In a source checkout this remains useful when the process was launched
    # from an unrelated directory.  In a wheel, the candidate has no runtime
    # layout and is harmless.
    bases.append(Path(__file__).resolve().parents[2])
    seen: set[Path] = set()
    for base in bases:
        for candidate in _ancestors(base):
            if candidate in seen:
                continue
            seen.add(candidate)
            if _has_runtime_layout(candidate):
                return candidate
    return None


def runtime_root(start: str | Path | None = None) -> Path:
    """Return the highest-priority runtime asset root.

    A checkout is preferred when invoked from that checkout; packaged assets
    are the fallback for installed distributions and arbitrary working dirs.
    """
    root = find_project_root(start)
    if root is not None:
        return root
    return PACKAGE_ASSET_ROOT


def resolve_config_dir(config_dir: str | Path | None = None) -> Path:
    """Resolve a configuration directory while preserving explicit paths."""
    if config_dir is not None:
        candidate = Path(config_dir).expanduser().resolve()
        if (candidate / "promptwise.yaml").is_file():
            return candidate
        nested = candidate / "config"
        if (nested / "promptwise.yaml").is_file():
            return nested
        return candidate

    env_dir = os.environ.get(CONFIG_ENV)
    if env_dir:
        candidate = Path(env_dir).expanduser().resolve()
        if (candidate / "promptwise.yaml").is_file():
            return candidate

    root = find_project_root()
    if root is not None and (root / "config").is_dir():
        return root / "config"
    return PACKAGE_ASSET_ROOT / "config"


def resolve_asset(relative: str | Path, *, root: str | Path | None = None) -> Path:
    """Resolve a repository-relative runtime asset.

    ``root`` is useful for tests and explicit caller-owned data.  Otherwise
    checkout assets win, followed by package-bundled assets.
    """
    relative_path = Path(relative)
    if relative_path.is_absolute():
        return relative_path
    base = Path(root).expanduser().resolve() if root is not None else runtime_root()
    candidate = base / relative_path
    if candidate.exists() or root is not None:
        return candidate
    return PACKAGE_ASSET_ROOT / relative_path


def resolve_skill_dir(directory: str | Path | None = None) -> Path:
    """Resolve the configured skill directory across source and wheel installs."""
    configured = Path(directory or "skill_packs")
    if configured.is_absolute():
        return configured
    candidate = runtime_root() / configured
    if candidate.is_dir():
        return candidate
    return PACKAGE_ASSET_ROOT / configured
