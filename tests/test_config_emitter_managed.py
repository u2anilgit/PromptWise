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


def test_premarker_user_content_preserved():
    # user wrote a title ABOVE the managed block; resync must keep it
    first = merge_managed(None, NEW)
    with_head = "# My own title\n\n" + first
    second = merge_managed(with_head, "# acme\n\nMethod: NEW.\n")
    assert "# My own title" in second          # head above block survives
    assert "NEW." in second                     # managed region still refreshed
    assert second.count("promptwise:managed:start") == 1


def test_lone_start_marker_is_rebuilt_not_conflicted():
    # corrupted managed file: start marker present, end marker missing
    corrupted = "<!-- promptwise:managed:start v=1 hash=dead -->\nstale body\n"
    out = merge_managed(corrupted, NEW)          # must NOT raise ConfigConflict
    assert out.count("promptwise:managed:start") == 1   # exactly one block, no dup
    assert MANAGED_END in out
    assert "stale body" not in out               # corrupted region rebuilt


def test_crlf_frontmatter_detected():
    mdc = "---\r\ndescription: x\r\nalwaysApply: true\r\n---\r\n\r\n# body\r\nMethod: m.\r\n"
    out = merge_managed(None, mdc)
    assert out.startswith("---")                 # frontmatter kept above block
    assert out.index("---") < out.index("promptwise:managed:start")


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


def test_windsurf_is_a_real_target(tmp_path):
    b = GovernanceBundle(project="acme", policy_summary=["Budget cap $5/day"])
    res = ConfigEmitter().sync(b, tmp_path, targets=["windsurf"])
    assert res == {".windsurfrules": "written"}
    assert "Budget cap $5/day" in (tmp_path / ".windsurfrules").read_text(encoding="utf-8")


def test_jetbrains_is_a_real_target(tmp_path):
    b = GovernanceBundle(project="acme", policy_summary=["Budget cap $5/day"])
    res = ConfigEmitter().sync(b, tmp_path, targets=["jetbrains"])
    assert res == {".aiassistant/rules/promptwise.md": "written"}
    text = (tmp_path / ".aiassistant" / "rules" / "promptwise.md").read_text(encoding="utf-8")
    assert "Budget cap $5/day" in text


def test_windsurf_sync_is_non_destructive(tmp_path):
    b = GovernanceBundle(project="acme", policy_summary=["Budget cap $5/day"])
    e = ConfigEmitter()
    e.sync(b, tmp_path, targets=["windsurf"])
    rules = tmp_path / ".windsurfrules"
    rules.write_text(rules.read_text(encoding="utf-8") + "\n- my note\n", encoding="utf-8")
    b2 = GovernanceBundle(project="acme", policy_summary=["Budget cap $9/day"])
    e.sync(b2, tmp_path, targets=["windsurf"])
    text = rules.read_text(encoding="utf-8")
    assert "Budget cap $9/day" in text
    assert "my note" in text


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


# ── Copilot path-scoped instruction files ───────────────────────────────────
def test_copilot_path_scoped_files_emitted(tmp_path):
    b = GovernanceBundle(project="acme", path_rules={"src/**/*.ts": ["Use strict mode", "No any"]})
    res = ConfigEmitter().sync(b, tmp_path, targets=["copilot"])
    scoped = ".github/instructions/src-ts.instructions.md"
    assert ".github/copilot-instructions.md" in res  # main file still emitted
    assert scoped in res                              # plus the path-scoped file
    text = (tmp_path / scoped).read_text(encoding="utf-8")
    assert 'applyTo: "src/**/*.ts"' in text
    assert "Use strict mode" in text


def test_glob_slug_collision_disambiguated(tmp_path):
    # two distinct globs that slug identically must NOT overwrite each other
    b = GovernanceBundle(project="acme", path_rules={"src/**/*.ts": ["A"], "src/*.ts": ["B"]})
    res = ConfigEmitter().sync(b, tmp_path, targets=["copilot"])
    scoped = [k for k in res if k.startswith(".github/instructions/")]
    assert len(scoped) == 2  # both rule sets emitted, no silent drop


def test_no_path_rules_means_no_scoped_files(tmp_path):
    res = ConfigEmitter().sync(GovernanceBundle(project="acme"), tmp_path, targets=["copilot"])
    assert res == {".github/copilot-instructions.md": "written"}  # unchanged behavior


def test_path_scoped_files_are_non_destructive(tmp_path):
    b = GovernanceBundle(project="acme", path_rules={"api/**": ["Frozen — no edits"]})
    e = ConfigEmitter()
    e.sync(b, tmp_path, targets=["copilot"])
    scoped = tmp_path / ".github/instructions/api.instructions.md"
    scoped.write_text(scoped.read_text(encoding="utf-8") + "\n- my hand note\n", encoding="utf-8")
    e.sync(b, tmp_path, targets=["copilot"])  # regenerate
    assert "my hand note" in scoped.read_text(encoding="utf-8")
