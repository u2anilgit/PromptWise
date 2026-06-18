"""Agent detector sniffs which coding-agent config files a repo carries (read-only)."""
from __future__ import annotations

from pathlib import Path

from promptwise.core.agent_detector import DetectionResult, detect_agents


def _snapshot(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")}


def test_claude_md_detected(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# rules", encoding="utf-8")
    result = detect_agents(tmp_path)
    assert "claude" in result.targets


def test_claude_dir_detected(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    result = detect_agents(tmp_path)
    assert "claude" in result.targets


def test_cursor_mdc_rule_detected(tmp_path: Path):
    rules = tmp_path / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (rules / "x.mdc").write_text("rule", encoding="utf-8")
    result = detect_agents(tmp_path)
    assert "cursor" in result.targets


def test_cursorrules_file_detected(tmp_path: Path):
    (tmp_path / ".cursorrules").write_text("rule", encoding="utf-8")
    result = detect_agents(tmp_path)
    assert "cursor" in result.targets


def test_agents_md_detected_as_codex(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# agents", encoding="utf-8")
    result = detect_agents(tmp_path)
    assert "codex" in result.targets


def test_agents_override_adds_confidence(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# agents", encoding="utf-8")
    base = detect_agents(tmp_path).confidence["codex"]
    (tmp_path / "AGENTS.override.md").write_text("# override", encoding="utf-8")
    boosted = detect_agents(tmp_path).confidence["codex"]
    assert boosted > base


def test_copilot_instructions_detected(tmp_path: Path):
    gh = tmp_path / ".github"
    gh.mkdir()
    (gh / "copilot-instructions.md").write_text("# copilot", encoding="utf-8")
    result = detect_agents(tmp_path)
    assert "copilot" in result.targets


def test_copilot_instructions_dir_detected(tmp_path: Path):
    (tmp_path / ".github" / "instructions").mkdir(parents=True)
    result = detect_agents(tmp_path)
    assert "copilot" in result.targets


def test_gemini_md_detected(tmp_path: Path):
    (tmp_path / "GEMINI.md").write_text("# gemini", encoding="utf-8")
    result = detect_agents(tmp_path)
    assert "gemini" in result.targets


def test_multiple_agents_ranked_by_confidence(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# claude", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# agents", encoding="utf-8")
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    (tmp_path / ".cursor" / "rules" / "x.mdc").write_text("rule", encoding="utf-8")
    result = detect_agents(tmp_path)
    assert set(["claude", "codex", "cursor"]).issubset(set(result.targets))
    # ranked by confidence descending
    confs = [result.confidence[k] for k in result.targets]
    assert confs == sorted(confs, reverse=True)
    # fingerprints record matched paths
    assert result.fingerprints["claude"]
    assert result.fingerprints["cursor"]


def test_tie_break_stable_by_key(tmp_path: Path):
    # CLAUDE.md and GEMINI.md are both primary-file hits -> equal confidence
    (tmp_path / "CLAUDE.md").write_text("# claude", encoding="utf-8")
    (tmp_path / "GEMINI.md").write_text("# gemini", encoding="utf-8")
    result = detect_agents(tmp_path)
    assert result.confidence["claude"] == result.confidence["gemini"]
    assert result.targets.index("claude") < result.targets.index("gemini")


def test_empty_repo_defaults_to_codex(tmp_path: Path):
    result = detect_agents(tmp_path)
    assert result.targets == ["codex"]
    assert result.confidence == {"codex": 0.5}
    assert result.fingerprints["codex"]  # carries a default note


def test_returns_detection_result_type(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# claude", encoding="utf-8")
    result = detect_agents(tmp_path)
    assert isinstance(result, DetectionResult)
    assert isinstance(result.targets, list)
    assert isinstance(result.confidence, dict)
    assert isinstance(result.fingerprints, dict)


def test_accepts_str_path(tmp_path: Path):
    (tmp_path / "GEMINI.md").write_text("# gemini", encoding="utf-8")
    result = detect_agents(str(tmp_path))
    assert "gemini" in result.targets


def test_detector_writes_nothing(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# claude", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# agents", encoding="utf-8")
    before = _snapshot(tmp_path)
    detect_agents(tmp_path)
    after = _snapshot(tmp_path)
    assert before == after


def test_detector_writes_nothing_on_empty_repo(tmp_path: Path):
    before = _snapshot(tmp_path)
    detect_agents(tmp_path)
    after = _snapshot(tmp_path)
    assert before == after
