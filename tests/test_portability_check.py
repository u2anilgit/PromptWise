"""Phase 7 §7.4 — cross-host portability check + host-neutral CI-snippet emitter.

The check validates that the emitted governance configs for every supported host
are present, well-formed, and in sync with the current skill/agent surface, and
reports drift precisely (which host, what is missing/stale). The CI-snippet
emitter produces a host-neutral pipeline that runs the governance gates using
tiers/families only — no branded model ids.
"""
from promptwise.core.config_emitter import ConfigEmitter, GovernanceBundle, TARGETS
from promptwise.core.portability_check import (
    build_surface_bundle,
    check_portability,
    emit_ci_snippet,
)


def _bundle(packs=("dev", "security")):
    return GovernanceBundle(
        project="acme",
        packs=list(packs),
        policy_summary=["the compliance gate is non-negotiable"],
    )


def _seed(root, bundle, targets=None):
    """Emit the configs for a bundle into a fresh repo root."""
    ConfigEmitter().sync(bundle, root, targets, mode="apply")


# ── PASS: every host present + well-formed + in sync ──────────────────────────
def test_passes_when_all_configs_present_and_in_sync(tmp_path):
    b = _bundle()
    _seed(tmp_path, b)
    rep = check_portability(tmp_path, bundle=b)
    assert rep.ok
    assert rep.drift == []
    assert {h.host for h in rep.hosts} == set(TARGETS)
    assert all(h.present and h.in_sync and h.well_formed for h in rep.hosts)


# ── FLAG: a missing emitted config, naming the host ───────────────────────────
def test_flags_missing_config_naming_host(tmp_path):
    b = _bundle()
    _seed(tmp_path, b)
    (tmp_path / TARGETS["gemini"]).unlink()
    rep = check_portability(tmp_path, bundle=b)
    assert not rep.ok
    assert any("gemini" in d for d in rep.drift)
    gem = next(h for h in rep.hosts if h.host == "gemini")
    assert not gem.present


# ── FLAG: a stale emitted config, naming the host ─────────────────────────────
def test_flags_stale_config_naming_host(tmp_path):
    _seed(tmp_path, _bundle())
    # the surface changes (a pack is added) but configs were not re-emitted
    drifted = _bundle(packs=("dev", "security", "devops"))
    rep = check_portability(tmp_path, bundle=drifted)
    assert not rep.ok
    assert any("claude" in d and "stale" in d.lower() for d in rep.drift)
    claude = next(h for h in rep.hosts if h.host == "claude")
    assert claude.present and not claude.in_sync


# ── surface bundle reflects skill_packs / agents / commands ───────────────────
def test_build_surface_bundle_reflects_repo_surface(tmp_path):
    (tmp_path / "skill_packs" / "dev").mkdir(parents=True)
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "reviewer.md").write_text("x", encoding="utf-8")
    (tmp_path / "commands").mkdir()
    (tmp_path / "commands" / "route.md").write_text("y", encoding="utf-8")
    b = build_surface_bundle(tmp_path)
    assert "dev" in b.packs
    # surface state is captured so any later change is detectable as drift
    assert "fingerprint" in " ".join(b.rules).lower()


def test_surface_change_moves_the_fingerprint(tmp_path):
    (tmp_path / "skill_packs" / "dev").mkdir(parents=True)
    fp1 = " ".join(build_surface_bundle(tmp_path).rules)
    (tmp_path / "skill_packs" / "security").mkdir()
    fp2 = " ".join(build_surface_bundle(tmp_path).rules)
    assert fp1 != fp2


# ── CI snippet: host-neutral, no branded model ids ────────────────────────────
_BRANDED = [
    "claude", "opus", "sonnet", "haiku", "anthropic",
    "gpt", "openai", "codex", "gemini", "llama", "mistral", "cohere",
]


def test_ci_snippet_is_host_neutral_no_branded_ids():
    snip = emit_ci_snippet()
    low = snip.lower()
    for token in _BRANDED:
        assert token not in low, f"CI snippet leaks a branded id: {token!r}"
    # it runs the governance gates and speaks tiers/families only
    assert "security" in low and "quality" in low
    assert any(t in low for t in ("fast", "balanced", "powerful"))
