"""tool_profiles -- how much of the tool surface a session pays for.

Every host injects every tool definition and JSON schema into context at session
start, before the user has typed anything. That is a fixed token cost paid
whether or not a single PromptWise tool is ever called, and it is by a wide
margin the largest cost this plugin imposes on a session.

A profile is a named subset. `full` is always one `expand_tool_surface` call
away, so nothing is ever permanently unreachable -- the tax becomes opt-in
rather than mandatory.

An unknown profile name resolves to the full surface, never to an empty one: a
server exposing zero tools is indistinguishable from a broken server, and a typo
in an env var should not look like an outage.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover - PyYAML is a declared dependency
    yaml = None  # type: ignore

_ENV = "PROMPTWISE_TOOL_PROFILE"
DEFAULT_PROFILE = "standard"
FULL_PROFILE = "full"

_OVERRIDE: str | None = None
_CACHE: dict | None = None


def _config_path() -> Path:
    from promptwise.asset_paths import resolve_asset
    local = Path("config") / "tool_profiles.yaml"
    return local if local.is_file() else resolve_asset("config/tool_profiles.yaml")


def _load() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    data: dict = {}
    try:
        p = _config_path()
        if yaml is not None and p.is_file():
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict) and isinstance(raw.get("profiles"), dict):
                data = raw["profiles"]
    except Exception:
        data = {}
    _CACHE = data
    return data


def reset_cache() -> None:
    """Drop the parsed-config cache (tests, and reload_config)."""
    global _CACHE
    _CACHE = None


def profile_names() -> list[str]:
    return sorted(set(list(_load().keys()) + [FULL_PROFILE]))


def profile_members(profile: str, _seen: frozenset[str] | None = None) -> list[str]:
    """Tool names in a profile, resolving its `extends` chain.

    `_seen` guards a cyclic or self-referential `extends` in a hand-edited
    config: a cycle should cost the cycle, not the process.
    """
    profiles = _load()
    entry = profiles.get(profile)
    if not isinstance(entry, dict):
        return []
    seen = (_seen or frozenset()) | {profile}
    names: list[str] = []
    parent = entry.get("extends")
    if parent and str(parent) not in seen:
        names.extend(profile_members(str(parent), seen))
    names.extend(str(n) for n in (entry.get("tools") or []))
    out: list[str] = []
    marked: set[str] = set()
    for n in names:
        if n not in marked:
            marked.add(n)
            out.append(n)
    return out


def active_profile() -> str:
    if _OVERRIDE:
        return _OVERRIDE
    raw = os.environ.get(_ENV, "").strip().lower()
    return raw or DEFAULT_PROFILE


def set_active_profile(name: str) -> str:
    """Switch the profile for this process (what expand_tool_surface calls)."""
    global _OVERRIDE
    _OVERRIDE = (name or "").strip().lower() or None
    return active_profile()


def filter_tools(tools, profile: str | None = None):
    """The subset of `tools` a profile exposes. Never returns an empty list."""
    name = (profile or active_profile()).lower()
    if name == FULL_PROFILE:
        return tools
    members = set(profile_members(name))
    if not members:
        return tools  # unknown profile -> full surface, never an outage
    kept = [t for t in tools if getattr(t, "name", None) in members]
    return kept or tools
