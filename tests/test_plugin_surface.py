"""Phase 6 WP3 — plugin surface (slash commands + sub-agents + doctor).

Each command fronts a real MCP tool; each sub-agent has valid frontmatter; the
doctor health-check and bootstrap run without raising.
"""
import re
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMANDS = sorted((ROOT / "commands").glob("*.md"))
AGENTS = sorted((ROOT / "agents").glob("*.md"))


def _server_tool_names() -> set[str]:
    import promptwise.server as s
    return {t.name for t in s._TOOL_DEFS}


def _frontmatter(path):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", path.read_text(encoding="utf-8"), re.DOTALL)
    assert m, f"{path.name}: no frontmatter"
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


# ── commands ─────────────────────────────────────────────────────────────────
def test_commands_exist():
    names = {p.stem for p in COMMANDS}
    assert {"audit", "policy", "quality-gate", "cost", "budget", "security",
            "doctor", "summarize", "shard", "draft-story"} <= names


def test_every_command_has_description():
    problems = []
    for c in COMMANDS:
        meta, body = _frontmatter(c)
        if not meta.get("description"):
            problems.append(f"{c.name}: missing description")
        if len(body.strip()) < 20:
            problems.append(f"{c.name}: body too short")
    assert not problems, problems


def test_each_command_fronts_a_real_tool():
    tools = _server_tool_names()
    # these drive the CLI / core engine, not an MCP tool
    exempt = {"doctor", "scaffold"}
    problems = []
    for c in COMMANDS:
        if c.stem in exempt:
            continue
        body = c.read_text(encoding="utf-8")
        if not any(t in body for t in tools):
            problems.append(f"{c.name}: references no known MCP tool")
    assert not problems, problems


# ── agents ───────────────────────────────────────────────────────────────────
def test_every_agent_has_required_frontmatter():
    problems = []
    for a in AGENTS:
        meta, body = _frontmatter(a)
        for req in ("name", "description", "tools"):
            if not meta.get(req):
                problems.append(f"{a.name}: missing {req}")
        if len(body.strip()) < 40:
            problems.append(f"{a.name}: body too short")
    assert not problems, problems


def test_new_agents_present():
    names = {p.stem for p in AGENTS}
    assert {"cost-analyst", "security-scanner", "planner", "reviewer", "permission-analyst"} <= names


# ── doctor / bootstrap ───────────────────────────────────────────────────────
def test_doctor_reports_all_checks(tmp_path):
    from promptwise.core.doctor import run_diagnostics
    report = run_diagnostics(cwd=tmp_path)
    names = {c["check"] for c in report["checks"]}
    assert {"hooks registered", "state dir writable", "core modules import",
            "policy present", "model registry loads"} <= names
    assert isinstance(report["ok"], bool)


def test_bootstrap_is_idempotent(tmp_path):
    from promptwise.core.doctor import bootstrap
    r1 = bootstrap(cwd=tmp_path)
    r2 = bootstrap(cwd=tmp_path)
    assert r1["ok"] and r2["ok"]
    assert (tmp_path / ".promptwise").exists()


def test_doctor_format_report_is_readable(tmp_path):
    from promptwise.core.doctor import run_diagnostics, format_report
    text = format_report(run_diagnostics(cwd=tmp_path))
    assert "PromptWise doctor" in text and "overall:" in text
