"""Managed-block protocol: non-destructive regeneration of agent rules files."""
import pytest

from promptwise.core.config_emitter import (
    ConfigConflict,
    ConfigEmitter,
    GovernanceBundle,
    MANAGED_END,
    USER_HEADER,
    merge_managed,
)

NEW = "# acme — agent guidance\n\nMethod: PromptWise governed agile method.\n"


def test_absent_file_gets_block_plus_user_section():
    out = merge_managed(None, NEW)
    assert "promptwise:managed:start" in out
    assert MANAGED_END in out
    assert USER_HEADER in out
    assert "Method: PromptWise governed agile method." in out


def test_existing_marked_file_replaces_only_managed_region():
    first = merge_managed(None, NEW)
    edited = first + "\n- prefer pnpm; legacy api/ is frozen.\n"
    second = merge_managed(edited, "# acme\n\nMethod: NEW METHOD.\n")
    # managed body updated…
    assert "NEW METHOD." in second
    assert "PromptWise governed agile method." not in second
    # …user content preserved verbatim
    assert "prefer pnpm; legacy api/ is frozen." in second


def test_unmanaged_file_refused_without_adopt():
    with pytest.raises(ConfigConflict):
        merge_managed("# my hand-written CLAUDE.md\n", NEW)


def test_unmanaged_file_adopted_when_flagged():
    out = merge_managed("# my hand-written CLAUDE.md\n", NEW, adopt=True)
    assert "promptwise:managed:start" in out
    assert "my hand-written CLAUDE.md" in out  # wrapped, not destroyed


def test_idempotent_resync_is_byte_identical():
    first = merge_managed(None, NEW)
    second = merge_managed(first, NEW)
    assert first == second


def test_frontmatter_stays_above_managed_block():
    mdc = "---\ndescription: x\nalwaysApply: true\n---\n\n# body\n\nMethod: m.\n"
    out = merge_managed(None, mdc)
    assert out.startswith("---\n")  # frontmatter first, required by Cursor
    assert out.index("---") < out.index("promptwise:managed:start")


def test_sync_is_non_destructive(tmp_path):
    b = GovernanceBundle(project="acme", policy_summary=["Budget cap $5/day"])
    e = ConfigEmitter()
    e.sync(b, tmp_path, targets=["claude"])
    claude = tmp_path / "CLAUDE.md"
    # user appends notes below the managed block
    claude.write_text(claude.read_text(encoding="utf-8") + "\n- my note\n", encoding="utf-8")
    # regenerate with a changed bundle
    b2 = GovernanceBundle(project="acme", policy_summary=["Budget cap $9/day"])
    e.sync(b2, tmp_path, targets=["claude"])
    text = claude.read_text(encoding="utf-8")
    assert "Budget cap $9/day" in text   # managed region regenerated
    assert "my note" in text             # user note survived


def test_sync_check_mode_reports_drift(tmp_path):
    b = GovernanceBundle(project="acme", policy_summary=["x"])
    e = ConfigEmitter()
    res = e.sync(b, tmp_path, targets=["claude"], mode="check")
    assert res["CLAUDE.md"] == "drift"  # file absent => drift from desired
    e.sync(b, tmp_path, targets=["claude"], mode="apply")
    res2 = e.sync(b, tmp_path, targets=["claude"], mode="check")
    assert res2["CLAUDE.md"] == "in-sync"


def test_diff_preview_writes_nothing(tmp_path):
    b = GovernanceBundle(project="acme", policy_summary=["x"])
    e = ConfigEmitter()
    out = e.diff(b, tmp_path, targets=["claude"])
    assert out["CLAUDE.md"]["status"] == "create"
    assert not (tmp_path / "CLAUDE.md").exists()  # diff never writes


def test_from_context_regulated_enrichment():
    b = GovernanceBundle.from_context(
        {"project": "acme", "text": "Ensure HIPAA compliance for patient records"}
    )
    assert any("healthcare" in line for line in b.policy_summary)


# ── P3: per-agent emit depth ────────────────────────────────────────────────
def test_gemini_is_a_real_target(tmp_path):
    b = GovernanceBundle(project="acme", policy_summary=["Budget cap $5/day"])
    res = ConfigEmitter().sync(b, tmp_path, targets=["gemini"])
    assert res == {"GEMINI.md": "written"}
    assert "Budget cap $5/day" in (tmp_path / "GEMINI.md").read_text(encoding="utf-8")


def test_codex_aliases_to_agents(tmp_path):
    b = GovernanceBundle(project="acme")
    res = ConfigEmitter().sync(b, tmp_path, targets=["codex"])
    assert "AGENTS.md" in res  # codex -> AGENTS.md


def test_cursor_frontmatter_is_profile_driven():
    cur = ConfigEmitter().render(GovernanceBundle(project="acme"), "cursor")
    assert cur.startswith("---\n")
    assert "alwaysApply: true" in cur  # cursor profile has "always" mode
    assert "globs:" in cur             # cursor profile supports_globs


def test_diff_surfaces_byte_cap_warning(tmp_path):
    big = "x" * 40000
    b = GovernanceBundle(project="acme", rules=[big])
    out = ConfigEmitter().diff(b, tmp_path, targets=["agents"])
    warns = out["AGENTS.md"]["warnings"]
    assert any("max_bytes" in w for w in warns)  # Codex ~32 KiB cap surfaced


def test_diff_has_warnings_key(tmp_path):
    out = ConfigEmitter().diff(GovernanceBundle(project="acme"), tmp_path, targets=["claude"])
    assert "warnings" in out["CLAUDE.md"]
