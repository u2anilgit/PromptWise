# Installing PromptWise

PromptWise is self-contained Python (≥ 3.10). No external services or framework installs.

## 1. Get the code

```bash
git clone https://github.com/u2anilgit/PromptWise.git
cd PromptWise
```

## 2. Install

```bash
pip install -e .            # runtime
pip install -e ".[dev]"     # + pytest for development
```

This installs the engine and the `promptwise` / `promptwise-server` console scripts.

## 3. Register with your agent

### Claude Code (plugin)
The repo ships `.claude-plugin/plugin.json` (MCP server + `/promptwise` hub skill) and a
local `marketplace.json`. Add the marketplace, then enable the plugin:

```bash
claude marketplace add ./           # from the repo root
claude plugin install promptwise
```

Restart Claude Code, run `/mcp` — the `promptwise` tools appear. Run `/promptwise`.

### Any MCP host (Codex, Cursor, Gemini, …)
Point the host at the bundled `.mcp.json`, or add this server entry:

```jsonc
{
  "mcpServers": {
    "promptwise": {
      "command": "python",
      "args": ["-m", "promptwise.server"],
      "cwd": "/absolute/path/to/PromptWise",
      "env": { "PYTHONPATH": "/absolute/path/to/PromptWise/src" }
    }
  }
}
```

### Skill packs in another agent (portable)
Copy the packs into the agent's skills dir — same files run everywhere:

```bash
cp -r skill_packs/* ~/.codex/skills/        # or ~/.gemini/skills/ , .cursor/skills/
```

## 4. Verify

```bash
PYTHONPATH=src python -c "import promptwise.server as s; print(len(s._TOOL_DEFS), 'tools')"
PYTHONPATH=src python -c "from pathlib import Path; from promptwise.core import SkillLoader; sl=SkillLoader(Path('skill_packs')); sl.load_skills(); print(len(sl.skills),'packs')"
```

Expected: `69 tools` and `72 packs`.

## Data location

Runtime data (sessions, cost logs, tasks, ROI) lives in a local SQLite DB at
`~/.promptwise/promptwise.db`. Delete that file to reset all history.

## Corporate proxy / SSL

If `pip` fails with `SSLCertVerificationError` (HTTPS interception), set a trusted host:

```bash
pip install -e . --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

## Uninstall

```bash
pip uninstall promptwise
rm -rf ~/.promptwise          # optional: remove local data
```
