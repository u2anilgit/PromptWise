"""portability_check — one check that the governance surface stays consistent
across every supported host, plus a host-neutral CI-snippet emitter.

Phase 7 §7.4 (platform-reach hardening). Emitters already compile ONE governance
source into each agent's native rules file (``config_emitter``); this module adds
the missing guardrail: verify that the emitted configs for every supported host
are (a) present, (b) well-formed, and (c) in sync with the current skill/agent
surface (skill_packs / agents / commands), and report drift precisely.

Design notes:
  * Reuses ``ConfigEmitter`` for rendering + drift detection rather than
    duplicating any emit logic. Drift = the surface bundle re-rendered would
    change the file (``ConfigEmitter.sync(mode="check")`` -> "drift").
  * The surface is folded into a fingerprint carried in the bundle so that
    adding/removing a pack, agent, or command makes every host config go stale
    until it is re-emitted.
  * Stdlib only, offline, air-gap-safe. No network, no new dependency.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from promptwise.core.config_emitter import (
    ConfigEmitter,
    GovernanceBundle,
    MANAGED_END,
    TARGETS,
    _START_RE,
    _norm_target,
)

# Supported hosts == the emitter targets we can actually render a config for.
# Host-neutral note per host: the native rules file the host reads. (These are
# config-file conventions, not model ids.)
SUPPORTED_HOSTS: dict[str, str] = dict(TARGETS)

# Which repo directories make up the "surface" the configs must stay in sync with.
_SURFACE_DIRS = ("skill_packs", "agents", "commands")


# ── surface discovery ─────────────────────────────────────────────────────────
def discover_surface(repo_root: str | Path = ".") -> dict[str, list[str]]:
    """Return the current governance surface as sorted name lists.

    skill_packs -> family directory names; agents/commands -> markdown stems.
    Missing directories yield an empty list (never raises).
    """
    root = Path(repo_root)
    out: dict[str, list[str]] = {}
    for name in _SURFACE_DIRS:
        d = root / name
        if not d.is_dir():
            out[name] = []
        elif name == "skill_packs":
            out[name] = sorted(p.name for p in d.iterdir() if p.is_dir())
        else:
            out[name] = sorted(p.stem for p in d.glob("*.md"))
    return out


def surface_fingerprint(surface: dict[str, list[str]]) -> str:
    """Stable short hash of the surface; moves when any pack/agent/command changes."""
    blob = "\n".join(f"{k}:{','.join(surface.get(k, []))}" for k in _SURFACE_DIRS)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def build_surface_bundle(
    repo_root: str | Path = ".", *, project: str = "this project"
) -> GovernanceBundle:
    """Build the canonical governance bundle that the host configs must match.

    The active skill-pack families become the bundle's packs; the surface
    fingerprint (packs + agents + commands) is carried as a house rule so any
    surface change is detectable as drift in every host's emitted config.
    """
    surface = discover_surface(repo_root)
    fp = surface_fingerprint(surface)
    return GovernanceBundle(
        project=project,
        packs=surface["skill_packs"],
        rules=[
            f"Governance surface fingerprint: {fp}",
            f"Surface: {len(surface['skill_packs'])} pack families, "
            f"{len(surface['agents'])} agents, {len(surface['commands'])} commands",
        ],
    )


# ── report shapes ─────────────────────────────────────────────────────────────
@dataclass
class HostReport:
    host: str
    path: str
    present: bool
    in_sync: bool
    well_formed: bool
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "path": self.path,
            "present": self.present,
            "in_sync": self.in_sync,
            "well_formed": self.well_formed,
            "issues": self.issues,
        }


@dataclass
class PortabilityReport:
    ok: bool
    hosts: list[HostReport]
    drift: list[str]

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "drift": self.drift,
            "hosts": [h.to_dict() for h in self.hosts],
        }


# ── the check ─────────────────────────────────────────────────────────────────
def check_portability(
    repo_root: str | Path = ".",
    *,
    bundle: GovernanceBundle | None = None,
    hosts: list[str] | None = None,
) -> PortabilityReport:
    """Validate the emitted host configs against the current surface.

    For each supported host, report present / well-formed / in-sync, and collect
    precise drift messages naming the host and what is wrong (missing / stale /
    malformed). ``bundle`` defaults to the surface bundle for ``repo_root``.
    """
    root = Path(repo_root)
    emitter = ConfigEmitter()
    if bundle is None:
        bundle = build_surface_bundle(repo_root)
    host_keys = hosts or list(SUPPORTED_HOSTS)

    reports: list[HostReport] = []
    drift: list[str] = []
    for h in host_keys:
        rel = TARGETS[_norm_target(h)]
        dest = root / rel
        present = dest.exists()
        in_sync = False
        well_formed = False
        issues: list[str] = []

        if not present:
            issues.append("missing emitted config")
            drift.append(f"{h}: missing {rel} — run sync_agent_config to emit it")
        else:
            content = dest.read_text(encoding="utf-8")
            well_formed = bool(re.search(_START_RE, content)) and MANAGED_END in content
            if not well_formed:
                issues.append("managed block malformed (markers missing)")
                drift.append(f"{h}: {rel} managed block is malformed")
            # Drift = re-rendering the surface bundle would change the file.
            status = emitter.sync(bundle, root, [h], mode="check").get(rel)
            in_sync = status == "in-sync"
            if not in_sync:
                issues.append("stale: surface changed since last emit")
                drift.append(
                    f"{h}: {rel} is stale (surface drift; re-run sync_agent_config)"
                )

        reports.append(HostReport(h, rel, present, in_sync, well_formed, issues))

    ok = all(r.present and r.in_sync and r.well_formed for r in reports)
    return PortabilityReport(ok=ok, hosts=reports, drift=drift)


def format_report(rep: PortabilityReport) -> str:
    """Human-readable one-liner-per-host summary (doctor style)."""
    lines = [f"PromptWise portability — overall: {'OK' if rep.ok else 'DRIFT'}"]
    for h in rep.hosts:
        mark = "ok" if (h.present and h.in_sync and h.well_formed) else "drift"
        detail = "; ".join(h.issues) if h.issues else "present, well-formed, in sync"
        lines.append(f"  [{mark}] {h.host} ({h.path}): {detail}")
    if rep.drift:
        lines.append("drift:")
        lines += [f"  - {d}" for d in rep.drift]
    return "\n".join(lines)


# ── host-neutral CI-snippet emitter ───────────────────────────────────────────
def emit_ci_snippet() -> str:
    """Emit a generic, host-neutral pipeline snippet that runs the governance gates.

    Portable across pipeline runners (generic ``stages``/``steps`` shape, no
    vendor-locked syntax). Routing is expressed as tiers/families only — never a
    branded model id — so the same gate runs anywhere PromptWise runs.
    """
    return (
        "# PromptWise governance gate — host-neutral CI snippet (Phase 7 §7.4).\n"
        "# Portable across pipeline runners: generic stages, no vendor lock-in,\n"
        "# no branded model ids. Model routing is expressed as tiers/families only.\n"
        "stages:\n"
        "  - governance\n"
        "\n"
        "promptwise-governance-gate:\n"
        "  stage: governance\n"
        "  # Runs the same gates PromptWise enforces locally, now in your pipeline.\n"
        "  steps:\n"
        "    - name: security-suite\n"
        "      run: python -m promptwise gate security --fail-on high\n"
        "    - name: quality-gate\n"
        "      run: python -m promptwise gate quality --min PASS\n"
        "    - name: cross-host-portability\n"
        "      run: python -m promptwise gate portability\n"
        "  # Advisory routing policy — pick by tier/family, never a branded id.\n"
        "  routing:\n"
        "    default_tier: balanced       # fast | balanced | powerful\n"
        "    escalate_to: powerful        # high-stakes / regulated changes\n"
        "    families: [local, hosted]    # keep host-neutral; no vendor lock-in\n"
    )
