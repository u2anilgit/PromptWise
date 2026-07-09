"""core/installer_support - idempotent .mcp.json merge logic shared by
install.sh / install.ps1. Stdlib only (json + argparse + pathlib).

The one-line installers are intentionally thin shell orchestration: check
python, `pip install -e .`, then (for any MCP host other than Claude Code,
which gets its own `claude marketplace add` / `claude plugin install` path)
call `python -m promptwise.core.installer_support` to add/refresh the
promptwise server entry in a target .mcp.json - automating the "manual
.mcp.json edit" step INSTALL.md currently documents, without clobbering a
user's existing servers or a hand-edited promptwise entry.
"""
from __future__ import annotations

import json
from pathlib import Path

_SERVER_NAME = "promptwise"


def default_server_entry(project_dir: str) -> dict:
    """The exact server block INSTALL.md documents for "any MCP host"."""
    return {
        "command": "python",
        "args": ["-m", "promptwise.server"],
        "cwd": project_dir,
        "env": {"PYTHONPATH": f"{project_dir}/src"},
    }


def merge_mcp_json(existing: dict | None, project_dir: str) -> dict:
    """Add a promptwise server entry if one isn't already present. Preserves
    every other key/server untouched; never overwrites a pre-existing
    promptwise entry (a merge, not a reset, in case a human hand-tuned it)."""
    data = dict(existing) if isinstance(existing, dict) else {}
    servers = dict(data.get("mcpServers") or {})
    if _SERVER_NAME not in servers:
        servers[_SERVER_NAME] = default_server_entry(project_dir)
    data["mcpServers"] = servers
    return data


def write_mcp_json(path: str | Path, project_dir: str) -> dict:
    """Read path if it exists (malformed -> treated as empty, fail-soft),
    merge in the promptwise entry, and write back."""
    p = Path(path)
    existing: dict = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    merged = merge_mcp_json(existing, project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return merged


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Merge a promptwise MCP server entry into a target .mcp.json")
    ap.add_argument("--mcp-json", default=".mcp.json", help="path to the target .mcp.json")
    ap.add_argument("--project-dir", default=".", help="PromptWise project root (used for cwd/PYTHONPATH)")
    args = ap.parse_args(argv)

    project_dir = str(Path(args.project_dir).resolve())
    merged = write_mcp_json(args.mcp_json, project_dir)
    present = _SERVER_NAME in merged.get("mcpServers", {})
    print(f"Wrote {args.mcp_json} (promptwise server entry present: {present})")


if __name__ == "__main__":
    main()
