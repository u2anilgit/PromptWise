"""Phase 17.3 — web-agent single-file bundle.

A structurally different distribution mode from the IDE emitters in
config_emitter.py: no host config file to merge into, so no managed-block
protocol, no TARGETS entry, no sync_agent_config wiring. WebBundleEmitter
flattens a GovernanceBundle + selected skill packs into ONE pasteable file
for ChatGPT / Gemini / Claude.ai web chat.
"""
from __future__ import annotations

from pathlib import Path

from promptwise.core.config_emitter import GovernanceBundle
from promptwise.core.web_bundle import WebBundleEmitter

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skill_packs"


def test_render_includes_method_and_policy():
    b = GovernanceBundle(
        project="acme-pay",
        policy_summary=["Budget cap $5/day"],
        rules=["No secrets in code"],
    )
    out = WebBundleEmitter().render(b, skill_root=SKILL_ROOT)
    assert "acme-pay" in out
    assert "PromptWise governed agile method" in out
    assert "Budget cap $5/day" in out
    assert "No secrets in code" in out


def test_render_is_self_contained_single_file():
    # No IDE/CLI/MCP host required: the bundle explains itself and carries no
    # managed-block markers (those are the IDE-emitter protocol, not this one).
    out = WebBundleEmitter().render(GovernanceBundle(project="acme"), skill_root=SKILL_ROOT)
    assert "paste" in out.lower()
    assert "promptwise:managed:start" not in out


def test_render_inlines_active_pack_content():
    b = GovernanceBundle(project="acme", packs=["banking"])
    out = WebBundleEmitter().render(b, skill_root=SKILL_ROOT)
    assert "banking" in out
    # the pack's actual body (from skill_packs/industry/banking.md) is inlined
    assert "FINRA" in out or "AML" in out or "Basel" in out


def test_render_fails_soft_on_missing_pack():
    b = GovernanceBundle(project="acme", packs=["does-not-exist-pack"])
    out = WebBundleEmitter().render(b, skill_root=SKILL_ROOT)
    assert "does-not-exist-pack" in out
    assert "unavailable" in out.lower()


def test_render_can_exclude_packs():
    b = GovernanceBundle(project="acme", packs=["banking"])
    out = WebBundleEmitter().render(b, skill_root=SKILL_ROOT, include_packs=False)
    assert "Active expert packs" not in out


def test_write_creates_single_standalone_file(tmp_path):
    b = GovernanceBundle(project="acme", policy_summary=["x"])
    dest = tmp_path / "bundles" / "acme-web-agent.md"
    content = WebBundleEmitter().write(b, dest, skill_root=SKILL_ROOT)
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == content


def test_write_fully_overwrites_not_merges(tmp_path):
    # Unlike the IDE emitters, regenerating the bundle is a full replace —
    # there is no user-owned region to preserve.
    b1 = GovernanceBundle(project="acme", policy_summary=["v1"])
    dest = tmp_path / "bundle.md"
    WebBundleEmitter().write(b1, dest, skill_root=SKILL_ROOT)
    dest.write_text(dest.read_text(encoding="utf-8") + "\nmy hand-added note\n", encoding="utf-8")
    b2 = GovernanceBundle(project="acme", policy_summary=["v2"])
    WebBundleEmitter().write(b2, dest, skill_root=SKILL_ROOT)
    text = dest.read_text(encoding="utf-8")
    assert "v2" in text
    assert "v1" not in text
    assert "my hand-added note" not in text
