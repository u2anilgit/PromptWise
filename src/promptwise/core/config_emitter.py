"""config_emitter — compile ONE governance source into every agent's native rules file.

Pillar 1 (agent-neutral portability): the same policy + packs + method renders into
CLAUDE.md / AGENTS.md, .cursor/rules, .github/copilot-instructions.md, .clinerules,
and GEMINI.md. Non-destructive: only the managed block regenerates (see merge_managed).
Pure string + file generation. Stdlib only, no network.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Managed-block protocol (additive, non-destructive) ──────────────────────
# PromptWise owns ONLY the fenced region between these markers. Everything the
# user writes outside it is preserved verbatim across regenerations.
MANAGED_START = "<!-- promptwise:managed:start v=1 hash={h} -->"
MANAGED_END = "<!-- promptwise:managed:end -->"
_START_RE = r"<!-- promptwise:managed:start[^>]*-->"
USER_HEADER = "## Your notes (PromptWise will never edit below this line)"


class ConfigConflict(Exception):
    """Raised when a hand-authored (unmanaged) file would be clobbered."""


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_prefix, body). Prefix is '' when there is none.

    Cursor .mdc files require their YAML frontmatter on the first line, so it
    must stay ABOVE the managed markers rather than inside them.
    """
    if text.startswith("---\n"):
        m = re.match(r"---\n.*?\n---\n", text, flags=re.S)
        if m:
            return m.group(0), text[m.end():]
    return "", text


def merge_managed(existing: str | None, new_block: str, *, adopt: bool = False) -> str:
    """Return file content with ONLY the managed region replaced.

    Three cases:
      * file absent            -> managed block + empty user section beneath it
      * file has markers       -> replace just the managed region, keep user text
      * file present, unmarked -> refuse unless adopt=True (then wrap it below)
    """
    prefix, body = _split_frontmatter(new_block)
    body = body.strip("\n")
    h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
    block = f"{MANAGED_START.format(h=h)}\n{body}\n{MANAGED_END}"
    if existing is None:
        return f"{prefix}{block}\n\n{USER_HEADER}\n"
    if MANAGED_END in existing and re.search(_START_RE, existing):
        tail = existing.split(MANAGED_END, 1)[1]
        return f"{prefix}{block}{tail}"
    if not adopt:
        raise ConfigConflict("unmanaged file present; pass adopt=True to wrap it")
    return f"{prefix}{block}\n\n## Your notes\n{existing}"


@dataclass
class GovernanceBundle:
    """The single source of truth that gets emitted to every agent."""
    project: str = "this project"
    method: str = "PromptWise governed agile method"
    policy_summary: list[str] = field(default_factory=list)   # human-readable policy lines
    packs: list[str] = field(default_factory=list)            # active skill packs
    rules: list[str] = field(default_factory=list)            # extra house rules

    @classmethod
    def from_context(cls, args: dict) -> "GovernanceBundle":
        """Build a bundle from tool arguments, optionally enriched by intent.

        Backward-compatible superset of the plain constructor: the same
        project/policy_summary/packs/rules keys still apply. If ``text`` is
        supplied, a light context model adds regulated-domain and stack hints.
        """
        b = cls(
            project=args.get("project", "this project"),
            method=args.get("method", "PromptWise governed agile method"),
            policy_summary=list(args.get("policy_summary", [])),
            packs=list(args.get("packs", [])),
            rules=list(args.get("rules", [])),
        )
        text = args.get("text")
        if text:
            try:  # context enrichment is best-effort and never fatal
                from promptwise.core.context_model import build_context_model
                cm = build_context_model(text, args.get("repo_root", "."))
                if cm.regulated and cm.domain:
                    b.policy_summary.append(
                        f"Regulated domain ({cm.domain}): the compliance gate is non-negotiable"
                    )
                if cm.stack:
                    b.rules.append(f"Detected stack: {', '.join(cm.stack)}")
            except Exception:
                pass
        return b

    def _body(self) -> str:
        out: list[str] = []
        out.append(f"Method: {self.method}.")
        if self.policy_summary:
            out.append("\nGovernance policy (enforced via PromptWise):")
            out += [f"- {p}" for p in self.policy_summary]
        if self.packs:
            out.append("\nActive expert packs:")
            out += [f"- {p}" for p in self.packs]
        if self.rules:
            out.append("\nHouse rules:")
            out += [f"- {r}" for r in self.rules]
        return "\n".join(out)


# (filename, format-label). Each emitter returns file content.
TARGETS = {
    "claude": "CLAUDE.md",
    "agents": "AGENTS.md",
    "cursor": ".cursor/rules/promptwise.mdc",
    "copilot": ".github/copilot-instructions.md",
    "cline": ".clinerules",
    "gemini": "GEMINI.md",
}

# Detector key without its own emitter yet: Codex reads the shared AGENTS.md.
_TARGET_ALIASES = {"codex": "agents"}

# Emitter target key -> AgentProfile key (for byte caps, frontmatter, token budget).
_EMITTER_TO_PROFILE = {
    "claude": "claude", "agents": "codex", "cursor": "cursor",
    "copilot": "copilot", "gemini": "gemini",
}


def _norm_target(t: str) -> str:
    return _TARGET_ALIASES.get(t, t)


def _profile_for(target: str):
    """Return the AgentProfile for an emitter target, or None if unavailable."""
    key = _EMITTER_TO_PROFILE.get(_norm_target(target))
    if not key:
        return None
    try:
        from promptwise.core.agent_profiles import ProfileRegistry
        return ProfileRegistry().get(key)
    except Exception:
        return None


def _lint_warnings(content: str, target: str) -> list[str]:
    """Run the config linter against rendered content using the target's profile
    (byte cap, .mdc frontmatter, always-on token tax). Best-effort; never fatal.
    """
    prof = _profile_for(target)
    if prof is None:
        return []
    try:
        from promptwise.core.config_linter import ConfigLinter
        fmt = prof.targets[0].fmt if prof.targets else "md"
        res = ConfigLinter().lint(
            content,
            fmt=fmt,
            max_bytes=prof.max_bytes,
            always_apply="always" in (prof.activation_modes or []),
            token_budget=prof.always_on_token_budget,
        )
        return [f"{i.severity}: {i.message}" for i in res.issues]
    except Exception:
        return []


class ConfigEmitter:
    def emit_claude(self, b: GovernanceBundle) -> str:
        return f"# {b.project} — agent guidance (generated by PromptWise)\n\n{b._body()}\n"

    def emit_agents(self, b: GovernanceBundle) -> str:
        return f"# AGENTS.md — {b.project} (generated by PromptWise)\n\n{b._body()}\n"

    def emit_cursor(self, b: GovernanceBundle) -> str:
        # Cursor .mdc rules require YAML frontmatter; fields are profile-driven so
        # activation mode / glob-scoping follow the live Cursor profile.
        prof = _profile_for("cursor")
        modes = getattr(prof, "activation_modes", []) or ["always"]
        always = "always" in modes
        lines = ["---", "description: PromptWise governance + method"]
        if getattr(prof, "supports_globs", False):
            lines.append('globs: ["**/*"]')
        lines.append(f"alwaysApply: {'true' if always else 'false'}")
        lines.append("---")
        front = "\n".join(lines)
        return f"{front}\n\n# {b.project} — PromptWise governance\n\n{b._body()}\n"

    def emit_copilot(self, b: GovernanceBundle) -> str:
        return f"# Copilot instructions — {b.project} (generated by PromptWise)\n\n{b._body()}\n"

    def emit_gemini(self, b: GovernanceBundle) -> str:
        return f"# GEMINI.md — {b.project} (generated by PromptWise)\n\n{b._body()}\n"

    def emit_cline(self, b: GovernanceBundle) -> str:
        return f"# .clinerules — {b.project} (generated by PromptWise)\n\n{b._body()}\n"

    def render(self, bundle: GovernanceBundle, target: str) -> str:
        target = _norm_target(target)
        fn = getattr(self, f"emit_{target}", None)
        if fn is None:
            raise ValueError(f"unknown target '{target}' (known: {list(TARGETS)})")
        return fn(bundle)

    def render_for_profile(self, bundle: GovernanceBundle, profile) -> dict[str, str]:
        """Profile-driven render: return {relative_path: content} for each of a
        profile's target files. Falls back to the legacy ``render`` per key.

        ``profile`` is an ``AgentProfile`` from ``agent_profiles``. This is the
        dynamic mechanism — file paths and format come from declarative data,
        not branching logic.
        """
        out: dict[str, str] = {}
        for tf in profile.targets:
            # Reuse the matching legacy emitter when one exists; the profile key
            # ("claude"/"cursor"/…) maps onto emit_<key>.
            content = self.render(bundle, profile.key) if hasattr(self, f"emit_{profile.key}") else self.emit_agents(bundle)
            out[tf.path] = content
        return out

    def sync(
        self,
        bundle: GovernanceBundle,
        repo_root: str | Path,
        targets: list[str] | None = None,
        write: bool = True,
        *,
        mode: str | None = None,
        adopt: bool = False,
    ) -> dict[str, str]:
        """Render and reconcile the bundle into each target's native file.

        Non-destructive: writes go through ``merge_managed`` so user-authored
        content outside the managed block is preserved across regenerations.

        ``mode`` (optional) supersedes ``write`` when given:
          * "apply"            -> write merged files
          * "preview"/"diff"   -> return merged content, write nothing
          * "check"            -> report drift only ("drift" | "in-sync")
        Omitting ``mode`` keeps the legacy ``write`` boolean behavior.

        Returns {relative_path: status_or_content}. Only ever touches the files
        listed in TARGETS; an unmanaged hand-authored file yields a "conflict"
        entry (unless ``adopt=True``) rather than being overwritten.
        """
        if mode is not None:
            write = mode == "apply"
        root = Path(repo_root)
        chosen = targets or list(TARGETS)
        result: dict[str, str] = {}
        for t in chosen:
            t = _norm_target(t)
            rel = TARGETS[t]
            rendered = self.render(bundle, t)
            dest = root / rel
            existing = dest.read_text(encoding="utf-8") if dest.exists() else None
            try:
                merged = merge_managed(existing, rendered, adopt=adopt)
            except ConfigConflict as e:
                result[rel] = f"conflict: {e}"
                continue
            if mode == "check":
                result[rel] = "in-sync" if existing == merged else "drift"
                continue
            if write:
                if existing == merged:
                    result[rel] = "unchanged"
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(merged, encoding="utf-8")
                    result[rel] = "written"
            else:
                result[rel] = merged
        return result

    def diff(
        self,
        bundle: GovernanceBundle,
        repo_root: str | Path,
        targets: list[str] | None = None,
        *,
        adopt: bool = False,
    ) -> dict[str, dict]:
        """Preview step: return a unified diff per target without writing.

        {relative_path: {"status": "create|update|unchanged|conflict",
                         "diff": "<unified diff text>"}}.
        """
        root = Path(repo_root)
        chosen = targets or list(TARGETS)
        out: dict[str, dict] = {}
        for t in chosen:
            t = _norm_target(t)
            rel = TARGETS[t]
            rendered = self.render(bundle, t)
            dest = root / rel
            existing = dest.read_text(encoding="utf-8") if dest.exists() else None
            try:
                merged = merge_managed(existing, rendered, adopt=adopt)
            except ConfigConflict as e:
                out[rel] = {"status": "conflict", "diff": str(e)}
                continue
            if existing is None:
                status = "create"
            elif existing == merged:
                status = "unchanged"
            else:
                status = "update"
            ud = "".join(
                difflib.unified_diff(
                    (existing or "").splitlines(keepends=True),
                    merged.splitlines(keepends=True),
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                )
            )
            out[rel] = {"status": status, "diff": ud, "warnings": _lint_warnings(merged, t)}
        return out
