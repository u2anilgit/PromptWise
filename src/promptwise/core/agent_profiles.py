"""agent_profiles — built-in capability profiles for coding-agent config targets.

Each AgentProfile encodes the facts the config compiler needs to emit a
provider-correct instruction file (target path, format, byte caps, frontmatter,
glob/path-scoping support, activation modes, nesting, imports, token budget).

ProfileRegistry exposes the 5 built-in defaults and can shallow-merge scalar
overrides from config/agent_profiles/<key>.yaml onto them. Stdlib + PyYAML only;
no network. Loading is tolerant: missing PyYAML, an absent dir, or a malformed
file must not crash hard.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from pathlib import Path

try:  # PyYAML is already a PromptWise dependency (skill_loader.py, policy.py)
    import yaml
except Exception:  # pragma: no cover - tolerated; overrides simply skip
    yaml = None  # type: ignore


@dataclass
class TargetFile:
    path: str            # e.g. "CLAUDE.md", ".cursor/rules/promptwise.mdc"
    fmt: str             # "md" | "mdc"
    scope: str = "repo"  # "repo" | "path-scoped"


@dataclass
class AgentProfile:
    key: str                       # "claude" | "cursor" | "codex" | "copilot" | "gemini"
    display_name: str
    targets: list[TargetFile]
    max_bytes: int | None = None   # Codex truncates ~32 KiB
    frontmatter: bool = False      # Cursor .mdc requires YAML frontmatter
    supports_globs: bool = False   # Cursor/Copilot path-scoping
    activation_modes: list[str] = field(default_factory=list)  # cursor: always|auto|agent|manual
    nested_hierarchy: bool = False  # Codex: root->cwd concat, nearest wins
    supports_imports: bool = False  # Claude @path includes
    always_on_token_budget: int = 0  # 0 = no cap; Cursor ~2000 soft cap
    commands_first: bool = True    # lead with setup/test/build


# Fields that load_overrides will shallow-merge from YAML. "targets" is a list of
# dataclasses, so it is intentionally excluded from the simple scalar merge.
_SCALAR_FIELDS = {f.name for f in fields(AgentProfile)} - {"key", "targets"}


def _builtin_profiles() -> dict[str, AgentProfile]:
    return {
        "claude": AgentProfile(
            key="claude",
            display_name="Claude Code",
            targets=[TargetFile(path="CLAUDE.md", fmt="md")],
            max_bytes=None,
            supports_imports=True,   # Claude supports @path includes
            nested_hierarchy=True,   # CLAUDE.md discovered up the tree
        ),
        "codex": AgentProfile(
            key="codex",
            display_name="Codex",
            targets=[TargetFile(path="AGENTS.md", fmt="md")],
            # Codex truncates context around 32 KiB; also supports AGENTS.override.md
            # layering (a higher-priority file merged over AGENTS.md).
            max_bytes=32000,
            nested_hierarchy=True,   # root -> cwd concat, nearest wins
        ),
        "cursor": AgentProfile(
            key="cursor",
            display_name="Cursor",
            targets=[TargetFile(path=".cursor/rules/promptwise.mdc", fmt="mdc")],
            frontmatter=True,        # .mdc requires YAML frontmatter
            supports_globs=True,     # path-scoped rules via globs
            activation_modes=["always", "auto", "agent", "manual"],
            always_on_token_budget=2000,  # ~2000 soft cap for always-on rules
        ),
        "copilot": AgentProfile(
            key="copilot",
            display_name="GitHub Copilot",
            targets=[TargetFile(path=".github/copilot-instructions.md", fmt="md")],
            # path-scoped .github/instructions/*.instructions.md with applyTo frontmatter
            supports_globs=True,
        ),
        "gemini": AgentProfile(
            key="gemini",
            display_name="Gemini",
            targets=[TargetFile(path="GEMINI.md", fmt="md")],
        ),
    }


class ProfileRegistry:
    """Holds built-in AgentProfiles and optional YAML scalar overrides."""

    def __init__(self) -> None:
        self._profiles: dict[str, AgentProfile] = _builtin_profiles()

    def get(self, key: str) -> AgentProfile:
        """Return the profile for ``key``; raise KeyError if unknown."""
        return self._profiles[key]

    def all(self) -> dict[str, AgentProfile]:
        """Return a copy of all profiles keyed by agent key."""
        return dict(self._profiles)

    def load_overrides(self, config_dir: str | Path) -> None:
        """Shallow-merge config/agent_profiles/<key>.yaml scalars onto built-ins.

        Tolerant by design: an absent directory, an absent file, a missing
        PyYAML, or a malformed YAML file leaves built-ins unchanged.
        """
        if yaml is None:
            return
        base = Path(config_dir)
        if not base.is_dir():
            return
        for key in list(self._profiles):
            path = base / f"{key}.yaml"
            if not path.is_file():
                continue
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception:  # malformed YAML or unreadable file -> skip
                continue
            if not isinstance(raw, dict):
                continue
            updates = {k: v for k, v in raw.items() if k in _SCALAR_FIELDS}
            if updates:
                self._profiles[key] = replace(self._profiles[key], **updates)
