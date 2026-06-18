"""Tests for promptwise.core.agent_profiles (TDD-first)."""
from __future__ import annotations

import pytest

from promptwise.core.agent_profiles import (
    AgentProfile,
    ProfileRegistry,
    TargetFile,
)

BUILTIN_KEYS = {"claude", "cursor", "codex", "copilot", "gemini"}


def test_builtin_defaults_load_for_all_five_keys():
    reg = ProfileRegistry()
    profiles = reg.all()
    assert set(profiles) == BUILTIN_KEYS
    for key in BUILTIN_KEYS:
        prof = reg.get(key)
        assert isinstance(prof, AgentProfile)
        assert prof.key == key
        assert prof.display_name
        assert prof.targets and all(isinstance(t, TargetFile) for t in prof.targets)


def test_get_raises_keyerror_on_unknown():
    reg = ProfileRegistry()
    with pytest.raises(KeyError):
        reg.get("does-not-exist")


def test_claude_profile_facts():
    prof = ProfileRegistry().get("claude")
    assert prof.display_name == "Claude Code"
    assert prof.targets[0].path == "CLAUDE.md"
    assert prof.targets[0].fmt == "md"
    assert prof.supports_imports is True
    assert prof.nested_hierarchy is True
    assert prof.max_bytes is None


def test_codex_profile_facts():
    prof = ProfileRegistry().get("codex")
    assert prof.display_name == "Codex"
    assert prof.targets[0].path == "AGENTS.md"
    assert prof.targets[0].fmt == "md"
    assert prof.nested_hierarchy is True
    # Codex truncates around 32 KiB.
    assert prof.max_bytes == 32000


def test_cursor_profile_facts():
    prof = ProfileRegistry().get("cursor")
    assert prof.display_name == "Cursor"
    assert prof.targets[0].path == ".cursor/rules/promptwise.mdc"
    assert prof.targets[0].fmt == "mdc"
    assert prof.frontmatter is True
    assert prof.supports_globs is True
    assert prof.activation_modes == ["always", "auto", "agent", "manual"]
    assert len(prof.activation_modes) == 4
    assert prof.always_on_token_budget == 2000


def test_copilot_profile_facts():
    prof = ProfileRegistry().get("copilot")
    assert prof.display_name == "GitHub Copilot"
    assert prof.targets[0].path == ".github/copilot-instructions.md"
    assert prof.targets[0].fmt == "md"
    assert prof.supports_globs is True


def test_gemini_profile_facts():
    prof = ProfileRegistry().get("gemini")
    assert prof.display_name == "Gemini"
    assert prof.targets[0].path == "GEMINI.md"
    assert prof.targets[0].fmt == "md"


def test_load_overrides_merges_scalar_fields(tmp_path):
    cfg_dir = tmp_path / "agent_profiles"
    cfg_dir.mkdir()
    (cfg_dir / "codex.yaml").write_text(
        "display_name: Codex Custom\nmax_bytes: 65000\n",
        encoding="utf-8",
    )

    reg = ProfileRegistry()
    assert reg.get("codex").max_bytes == 32000  # baseline before override
    reg.load_overrides(cfg_dir)

    prof = reg.get("codex")
    assert prof.display_name == "Codex Custom"
    assert prof.max_bytes == 65000
    # untouched profiles remain at their built-in values
    assert reg.get("claude").display_name == "Claude Code"


def test_load_overrides_noop_when_dir_absent(tmp_path):
    reg = ProfileRegistry()
    missing = tmp_path / "nope"
    reg.load_overrides(missing)  # should not raise
    assert reg.get("codex").max_bytes == 32000


def test_load_overrides_tolerant_of_bad_file(tmp_path):
    cfg_dir = tmp_path / "agent_profiles"
    cfg_dir.mkdir()
    (cfg_dir / "claude.yaml").write_text(": : not valid yaml : :\n[", encoding="utf-8")
    reg = ProfileRegistry()
    reg.load_overrides(cfg_dir)  # must not crash hard
    assert reg.get("claude").display_name == "Claude Code"
