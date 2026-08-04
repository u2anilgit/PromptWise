# Installing PromptWise

PromptWise is self-contained Python (≥ 3.10). No external services or framework installs.

## 1. Get the code

```bash
git clone https://github.com/u2anilgit/PromptWise.git
cd PromptWise
```

## 2. Install

```bash
pip install -e .                    # runtime (lightweight, no embeddings)
pip install -e ".[dev]"             # + pytest for development
pip install -e ".[embeddings]"      # + local semantic cache / hybrid memory search
```

This installs the engine and the `promptwise` / `promptwise-server` console scripts.

### Optional: local embeddings (semantic cache + hybrid memory search)

By default PromptWise never installs embedding dependencies — `cache_lookup`/
`cache_store` are exact-match only and `query_memory` is keyword-ranked only,
same as always. Opting in via `pip install -e ".[embeddings]"` (or
`./install.sh --embeddings` / `./install.ps1 -Embeddings`) adds ~300MB of
local ML dependencies (`fastembed`/`onnxruntime`, no PyTorch) that run fully
offline — the first real embedding call downloads a small model (~100MB,
one-time, needs network) and every call after that is local ONNX inference,
never a network or LLM call. Nothing changes for anyone who skips this; run
the `embedding_status` tool any time to check whether it's installed and
ready. See `docs/PHASE19_ROADMAP.md` for the full design.

### From a built distribution (no editable checkout)

For CI or a non-dev install, build a wheel + sdist instead of installing in editable mode:

```bash
pip install build
python -m build                       # writes dist/promptwise-<version>-py3-none-any.whl + .tar.gz
pip install dist/promptwise-*.whl
```

The wheel/sdist ships the Python engine only (`src/promptwise/`) — `skill_packs/`,
`config/`, `hooks/`, and `.claude-plugin/` stay in the git checkout your MCP host
points `cwd`/`PYTHONPATH` at (see step 3). This mirrors the plugin's own model: the
engine is a normal installable package, but the governed assets it reads are
repo-relative, not bundled inside the wheel.

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

Expected: `107 tools` and `81 packs`.

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
