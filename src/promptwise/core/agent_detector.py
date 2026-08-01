"""Read-only detector for coding-agent config fingerprints in a repo.

Sniffs which AI coding agents a repository is configured for by checking for
the existence of well-known marker files/directories. Never writes to disk and
never touches the network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Confidence weights for the kind of evidence that matched.
PRIMARY = 0.9  # a canonical primary file (e.g. CLAUDE.md)
SECONDARY = 0.6  # a directory-only or secondary marker
OVERRIDE_BOOST = 0.05  # extra signal from an override/supplementary file
DEFAULT = 0.5  # empty-repo fallback


@dataclass
class DetectionResult:
    targets: list[str]  # ranked agent keys present, e.g. ["claude", "cursor"]
    confidence: dict[str, float]  # key -> 0..1
    fingerprints: dict[str, list[str]]  # key -> which paths matched


@dataclass
class _Probe:
    key: str
    hits: list[str] = field(default_factory=list)
    score: float = 0.0

    def add(self, path: str, weight: float) -> None:
        self.hits.append(path)
        self.score = max(self.score, weight)

    def boost(self, path: str, amount: float) -> None:
        if self.hits:
            self.hits.append(path)
            self.score = min(1.0, self.score + amount)


def _has_glob(directory: Path, pattern: str) -> bool:
    try:
        return any(True for _ in directory.glob(pattern))
    except OSError:
        return False


def detect_agents(repo_root: str | Path = ".") -> DetectionResult:
    """Detect which coding agents a repo is configured for (read-only)."""
    root = Path(repo_root)

    probes: dict[str, _Probe] = {}

    def probe(key: str) -> _Probe:
        return probes.setdefault(key, _Probe(key=key))

    # --- claude: CLAUDE.md OR .claude/ directory ---
    if (root / "CLAUDE.md").is_file():
        probe("claude").add("CLAUDE.md", PRIMARY)
    if (root / ".claude").is_dir():
        probe("claude").add(".claude/", SECONDARY)

    # --- codex: AGENTS.md (+ AGENTS.override.md adds confidence) ---
    if (root / "AGENTS.md").is_file():
        probe("codex").add("AGENTS.md", PRIMARY)
    if (root / "AGENTS.override.md").is_file():
        probe("codex").boost("AGENTS.override.md", OVERRIDE_BOOST)

    # --- cursor: .cursor/rules/*.mdc OR .cursorrules ---
    cursor_rules = root / ".cursor" / "rules"
    if cursor_rules.is_dir() and _has_glob(cursor_rules, "*.mdc"):
        probe("cursor").add(".cursor/rules/*.mdc", SECONDARY)
    if (root / ".cursorrules").is_file():
        probe("cursor").add(".cursorrules", PRIMARY)

    # --- copilot: .github/copilot-instructions.md OR .github/instructions/ ---
    if (root / ".github" / "copilot-instructions.md").is_file():
        probe("copilot").add(".github/copilot-instructions.md", PRIMARY)
    if (root / ".github" / "instructions").is_dir():
        probe("copilot").add(".github/instructions/", SECONDARY)

    # --- gemini: GEMINI.md ---
    if (root / "GEMINI.md").is_file():
        probe("gemini").add("GEMINI.md", PRIMARY)

    # --- windsurf: .windsurfrules ---
    if (root / ".windsurfrules").is_file():
        probe("windsurf").add(".windsurfrules", PRIMARY)

    # --- jetbrains: .aiassistant/ dir (rule "type" lives in IDE settings, not
    # a specific filename, so directory presence is the only file-level signal) ---
    if (root / ".aiassistant").is_dir():
        probe("jetbrains").add(".aiassistant/", SECONDARY)

    # --- cline: .clinerules ---
    if (root / ".clinerules").is_file():
        probe("cline").add(".clinerules", PRIMARY)

    # --- aider: CONVENTIONS.md -- SECONDARY, not PRIMARY: the filename is a
    # community convention also read by Cursor/Cline/Claude Code, not unique
    # to aider, so its presence alone is weaker evidence than e.g. CLAUDE.md ---
    if (root / "CONVENTIONS.md").is_file():
        probe("aider").add("CONVENTIONS.md", SECONDARY)

    # --- goose: .goosehints ---
    if (root / ".goosehints").is_file():
        probe("goose").add(".goosehints", PRIMARY)

    # --- openhands: .openhands/microagents/repo.md, or .openhands/ dir alone ---
    if (root / ".openhands" / "microagents" / "repo.md").is_file():
        probe("openhands").add(".openhands/microagents/repo.md", PRIMARY)
    elif (root / ".openhands").is_dir():
        probe("openhands").add(".openhands/", SECONDARY)

    # NOTE: no "grok" probe. Grok Build/Grok CLI has no rules file of its own
    # -- it natively auto-reads CLAUDE.md/AGENTS.md (see config_emitter.py's
    # _TARGET_ALIASES) -- so its presence isn't independently detectable; a
    # repo with CLAUDE.md correctly surfaces as "claude" already.

    matched = [p for p in probes.values() if p.hits]

    if not matched:
        # Empty-repo rule: AGENTS.md is the canonical cross-agent default.
        return DetectionResult(
            targets=["codex"],
            confidence={"codex": DEFAULT},
            fingerprints={"codex": ["(default: AGENTS.md is the cross-agent default)"]},
        )

    # Sort by confidence descending, stable tie-break by key name ascending.
    matched.sort(key=lambda p: (-p.score, p.key))

    return DetectionResult(
        targets=[p.key for p in matched],
        confidence={p.key: round(p.score, 4) for p in matched},
        fingerprints={p.key: p.hits for p in matched},
    )
